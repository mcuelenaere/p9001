import cv2
import cherrypy
import json
import numpy as np
import os

from threading import Thread, Event
from time import sleep


class ParkingDetector():
	def __init__(self, capture):
		self._cap = capture
		self._thread = Thread(target=self._run)
		self._stop_requested = False
		self._areas = []
		self._snapshot_requested = False
		self._empty_state = None
		self._mean_pixel_cutoff = 10
		self._obscured_areas = {}
		self._last_color_image = None
		self._last_raw_image = None
		self._event = Event()

	def start(self):
		self._thread.start()

	def stop(self):
		self._stop_requested = True

	def addPossiblyObscuredArea(self, left, right, top, bottom, name):
		self._areas.append([left, right, top, bottom, name])

	def takeSnapshotOfEmptyState(self):
		self._snapshot_requested = True

	def getObscuredAreas(self):
		return self._obscured_areas

	def getLastColorImage(self):
		return self._last_color_image

	def getLastRawImage(self):
		return self._last_raw_image

	def waitForNewData(self, timeout=None):
		self._event.wait(timeout)

	def getAreas(self):
		return self._areas

	def clearAreas(self):
		self._areas = []

	def _run(self):
		while True:
			ret, frame = cap.read()
			if ret:
				self._process(frame)
			sleep(.1)

	def _process(self, frame):
		self._event.clear()

		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		ret, thresholded = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
		if not ret:
			print('Could not threshold image')
			return

		if self._empty_state is not None and not self._snapshot_requested:
			# remove pixels that are always present
			thresholded = thresholded & ~self._empty_state

		if self._snapshot_requested:
			self._empty_state = thresholded
			self._snapshot_requested = False

		self._obscured_areas = {}
		for left, right, top, bottom, name in self._areas:
			mean_pixel_value = np.mean(thresholded[top:bottom, left:right])
			is_obscured = bool(mean_pixel_value > self._mean_pixel_cutoff)
			self._obscured_areas[name] = is_obscured

		# update member variables
		self._last_color_image = frame
		self._last_raw_image = thresholded

		# notify listeners
		self._event.set()


class HttpServer(object):
	def __init__(self, parking_detector):
		self._parking_detector = parking_detector

	@cherrypy.expose
	def index(self):
		raise cherrypy.HTTPRedirect('/static/index.html')

	def create_stream(self, quality, image_cb):
		boundary = "--streammjpeg"
		cherrypy.response.headers['Content-Type'] = "multipart/x-mixed-replace;boundary=" + boundary
		def stream():
			while True:
				image = image_cb()
				_, data = cv2.imencode(".jpeg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
				data = data.tostring()
				headers = "Content-Type: image/jpeg\r\nContent-Length: %d\r\n" % (len(data))
				yield boundary + "\r\n" + headers + "\r\n" + data + "\r\n"
				sleep(.1)
				self._parking_detector.waitForNewData()
		return stream()

	@cherrypy.expose
	def color_video_stream(self):
		return self.create_stream(75, lambda: self._parking_detector.getLastColorImage())
	color_video_stream._cp_config = {'response.stream': True}

	@cherrypy.expose
	def raw_video_stream(self):
		return self.create_stream(75, lambda: self._parking_detector.getLastRawImage())
	raw_video_stream._cp_config = {'response.stream': True}

	@cherrypy.expose
	def obscured_areas(self):
		obscured_areas = self._parking_detector.getObscuredAreas()
		cherrypy.response.headers['Content-Type'] = "application/json"
		return json.dumps({
			'areas': obscured_areas
		})

	@cherrypy.expose
	def add_area(self, name, left, right, top, bottom):
		self._parking_detector.addPossiblyObscuredArea(int(left), int(right), int(top), int(bottom), name)
		return ''

	@cherrypy.expose
	def get_areas(self):
		cherrypy.response.headers['Content-Type'] = "application/json"
		return json.dumps({
			'areas': tuple({
				'left': x[0],
				'right': x[1],
				'top': x[2],
				'bottom': x[3],
				'name': x[4]
			} for x in self._parking_detector.getAreas())
		})

	@cherrypy.expose
	def clear_areas(self):
		self._parking_detector.clearAreas()
		return ''

	@cherrypy.expose
	def snapshot_empty_state(self):
		self._parking_detector.takeSnapshotOfEmptyState()
		return ''

if __name__ == '__main__':
	cap = cv2.VideoCapture(0)
	try:
		parking_detector = ParkingDetector(cap)
		server = HttpServer(parking_detector)
		parking_detector.start()
		cherrypy.quickstart(server, '/', config={
			'/static': {
				'tools.staticdir.on': True,
				'tools.staticdir.dir': 'static',
				'tools.staticdir.root': os.path.abspath(os.path.dirname(__file__)),
				'tools.staticdir.index': 'index.html',
			}
		})
	finally:
		cap.release()
