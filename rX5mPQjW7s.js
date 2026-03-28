function rX5mPQjW7s(elementID) {
        if (elementID) {
            var a  = $('.carousel-indicators .active');
            a.toggleClass('active');
            a.next('.indicators').toggleClass('active');
            $("#"+elementID).parents('.fangate-slider-content').toggleClass('move-left');
            var currentdiv = $("#"+elementID).parents('.fangate-slider-content');
            var currentzindex = currentdiv.css("z-index");
            $("#"+elementID).parents('.fangate-slider-content').next().toggleClass('upcomming-slide').css('z-index',parseInt(currentzindex)+1);
        }
        currentSlideCardHeight();
    }