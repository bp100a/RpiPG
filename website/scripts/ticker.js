/**
 * @author Matt Hinchliffe <http://www.maketea.co.uk>
 * @modified 13/05/2011
 * @title Simple jQuery News Ticker
 */
(function($)
{
    $.fn.Ticker = function(options)
    {
        var defaults = {

            // Time to display each news item. (integer, milliseconds)
            pause: 5000,

            // Time taken to fade in next news item. (integer, milliseconds)
            fadeIn: 800,

            // Time taken to fade out current news item. (integer, milliseconds)
            fadeOut: 800,

            // Pause between displaying each item when fading between items. (integer, milliseconds)
            delay: 500,

            // Next news item typed out one character at a time. If false item will fade in. (boolean)
            typewriter: true,

            // Time to type each character if using the typewriter effect (integer, milliseconds)
            speed: 35,

            // Character to use to mimic a computer cursor if using the typewriter effect (string|boolean)
            cursor: '_'
        };

        // Merge default options with user options
        var opts = $.extend({}, defaults, options);

        return $(this).each(function()
        {
            var list = $(this), typewriter = {}, interval;

            // Activate ticker and display first item
            list
                .addClass('ticker-active')
                .children(':first')
                .css('display', 'block');

            function changeItem()
            {
                var item = list.children(':first'),
                    next = item.next(),
                    copy = item.clone();

                clearTimeout(interval);

                // Append copy of current item to bottom of list
                $(copy)
                    .css('display', 'none')
                    .appendTo(list);

                // Fade current item out, remove from DOM then animate the next item
                item.fadeOut(opts.fadeOut, function()
                {
                    $(this).remove();

                    // Animate
                    if (opts.typewriter)
                    {
                        typewriter.string = next.text();

                        next
                            .text('')
                            .css('display', 'block');

                        typewriter.count = 0;
                        typewriter.timeout = setInterval(type, opts.speed);
                    }
                    else
                    {
                        next
                            .delay(opts.delay)
                            .fadeIn(opts.fadeIn, function ()
                            {
                                setTimeout(changeItem, opts.pause);
                            });
                    }
                });
            }

            function type()
            {
                typewriter.count++;
                var text =  typewriter.string.substring(0, typewriter.count);
                if (typewriter.count >= typewriter.string.length)
                {
                    clearInterval(typewriter.timeout);
                    setTimeout(changeItem, opts.pause);
                }
                else if (opts.cursor)
                {
                    text+= ' ' + opts.cursor;
                }

                list
                    .children(':first')
                    .text(text);
            }

            // Test there are more items to display then start ticker
            if (list.find('li').length > 1 )
            {
                interval = setTimeout(changeItem, opts.pause);
            }
        });
    };

    $('.ticker').Ticker();

})(jQuery);