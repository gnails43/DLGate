function gateEmailVerificationNextSlide() {

    var a  = $('.carousel-indicators .active');
    a.toggleClass('active');
    a.next('.indicators').toggleClass('active');
    $("#email_to_downloads_next").parents('.fangate-slider-content').toggleClass('move-left');

    var currentdiv = $("#email_to_downloads_next").parents('.fangate-slider-content');
    var currentzindex = currentdiv.css("z-index");
    var gate_design_template = $("#gate_design_template").val();

    $("#email_to_downloads_next").parents('.fangate-slider-content').next().toggleClass('upcomming-slide').css('z-index',parseInt(currentzindex)+1);
    
    if (gate_design_template == 'modern') {
        var currentSlideHeight = $('.fangate-slider-content').not('.move-left').first().height();
        $('.carousel-inner').height(currentSlideHeight);
    }
}