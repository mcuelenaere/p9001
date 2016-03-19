(function() {
    function call(method, args) {
        return $.ajax({
            url: '/' + method,
            data: args
        }).fail(function (err) {
            console.error(err);
        })
    }

    $('#snapshot').on('click', function () {
        call('snapshot_empty_state');
    });

    var resolution = [640, 480];

    function createArea(name, left, right, top, bottom) {
        var base_offs = $color_stream.offset();
        $('<div>').addClass('parking-area').css({
            'position': 'absolute',
            'top': base_offs.top + top + 'px',
            'left': base_offs.left + left,
            'height': (bottom - top) + 'px',
            'width': (right - left) + 'px',
        }).attr('data-area-name', name).text(name).appendTo($(document.body));
    }

    var lastClick = null;
    var $color_stream = $('#color_stream');
    $color_stream.on('click', function (ev) {
        var w = $color_stream.width(),
            h = $color_stream.height(),
            x = parseInt((ev.offsetX / w) * resolution[0]),
            y = parseInt((ev.offsetY / h) * resolution[1]);

        if (lastClick === null) {
            lastClick = {x:x, y:y};
        } else {
            var name = prompt('What\'s the name of this area?', ''),
                area = [lastClick.x, x, lastClick.y, y];

            createArea(name, area[0], area[1], area[2], area[3]);

            call('add_area', {
                name: name,
                left: area[0],
                right: area[1],
                top: area[2],
                bottom: area[3]
            });
            // reset
            lastClick = null;
        }
    });

    $('#clear').on('click', function () {
        call('clear_areas');
        $('[data-area-name]').remove();
    });

    setInterval(function () {
        call('obscured_areas').done(function (data) {
            $.each(data.areas, function (name, is_obscured) {
                var $target = $('[data-area-name="' + name + '"]');
                if (is_obscured) {
                    $target.addClass('parking-busy').removeClass('parking-free');
                } else {
                    $target.addClass('parking-free').removeClass('parking-busy');
                }
            });
        });
    }, 500);


    call('get_areas').done(function (data) {
        console.log(data);
        $.each(data.areas, function (_, area) {
            console.log(area);
            createArea(area.name, area.left, area.right, area.top, area.bottom);
        });
    });
})();
