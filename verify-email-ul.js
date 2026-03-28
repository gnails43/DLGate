var is_captcha = 0;
var warningIcon = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7.99999 5.83333V8.5M6.85394 2.42744L1.86462 10.8186C1.33616 11.7073 1.97665 12.8333 3.01067 12.8333H12.9893C14.0233 12.8333 14.6638 11.7073 14.1353 10.8186L9.14603 2.42744C8.62921 1.55824 7.37076 1.55824 6.85394 2.42744Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><ellipse cx="7.99992" cy="10.3333" rx="0.666667" ry="0.666667" fill="currentColor"/></svg>';

$(document).ready(function ($)
{
    // event for subscribe for newsletter  ///
    $('.email_to_downloads').on('click', function (e)
    {
        var email_get      = $("#email_address").val().trim();
        var email_name_get = '';
        if($("#email_name").length) {

          email_name_get = $("#email_name").val().trim();
          // 
          if (email_name_get === '')
          {
              $(".name_error_email_name").hasClass('hype-invalid-feedback') 
                ? $(".name_error_email_name").html(warningIcon + "Please enter your name.").show().parent().addClass('is-invalid') 
                : $(".name_error_email_name").html("Please enter your name.").show().parent().addClass('has-error');

              $("#loader").hide();
              return false;

          }else{
            $('div').removeClass('has-error').removeClass('is-invalid');
            $(".name_error_email_name").html('').hide();
          }
        }
        // 
        if ($("#email_address").val() == '') {
            $(".name_error_email").hasClass('hype-invalid-feedback') 
                ? $(".name_error_email").html(warningIcon + "Please enter your email.").show().parent().addClass('is-invalid') 
                : $(".name_error_email").html("Please enter your email.").show().parent().addClass('has-error');

            $("#loader").hide();
            return false;

        }
        if ($("#email_address").val() != '')
        {
            var sEmail = $("#email_address").val().trim();
            if (!validateEmail(sEmail))
            {
                $(".name_error_email").show();
                $(".name_error_email").html('Please enter a valid email address.').parent().addClass('has-error');

                $(".name_error_email").hasClass('hype-invalid-feedback') 
                    ? $(".name_error_email").html(warningIcon + "Please enter a valid email address.").show().parent().addClass('is-invalid')
                    : $(".name_error_email").html("Please enter a valid email address.").show().parent().addClass('has-error');

                $("#loader").hide();
                return false;
            }
        }
        if ($("#email_address").val() != '')
        {
            var sEmail = $("#email_address").val().trim();
            $('div').removeClass('has-error').removeClass('is-invalid');
            $(".name_error_email").html('');
            $(".name_error_email").hide();
            //$(this).addClass('hy-loading-btn').prop('disabled', true);
            
            if (validateEmail(sEmail))
            {

               /* HYPE-109*/
                
               var email_address = $("#email_address").val();
               var fan_gate_id   =  $("#fan_gate_id").val();
               var iAttemptCount = 0;

               // Check cookie exist and then get the particular fangate email verify attempt
               if ($.cookie('teb3456767win')) {
                   var iAttemptCookie = JSON.parse($.cookie('teb3456767win'));
                   iAttemptCount = iAttemptCookie[fan_gate_id];
               }

               runEmailVerification();

               var max_attempsts_value = document.getElementById("captchalog").getAttribute("data-max-attempts");

               // If value of email attempt is equal to 5 then enable google captcha 
               if(iAttemptCount == (max_attempsts_value-1)) {
                  // get sitekey
                  is_captcha = 1;
                  $("#gatePreviewCaptcha").removeClass('hide');
                  var sitekey = document.getElementById("captchalog").getAttribute("data-sitekey");
                   grecaptcha.render('html_element', {
                   'sitekey' : sitekey,
                   });
               }
               
               
            } else {

                $(".name_error_email").hasClass('hype-invalid-feedback') 
                    ? $(".name_error_email").html(warningIcon + "Please enter a valid email address.").show().parent().addClass('is-invalid')
                    : $(".name_error_email").html("Please enter a valid email address.").show().parent().addClass('has-error');

                $("#loader").hide();
            }
        }
    });
    
    

});

/* code for google recaptcha */
/* HYPE-109 Revert back */

  $(document).ready(function() {

      var fan_gate_id   =  $("#fan_gate_id").val();
      var max_attempsts_value = document.getElementById("captchalog").getAttribute("data-max-attempts");
      var attempts = document.getElementById("captchalog").getAttribute("data-attempts");
      if ($.cookie('teb3456767win')) {

          var iAttemptCookie = JSON.parse($.cookie('teb3456767win'));
          var iAttemptCount = iAttemptCookie[fan_gate_id];


          $( "#overlay-modal-box" ).on('shown.bs.modal', function (e) {
            setTimeout(function(){

            if( (iAttemptCount && (iAttemptCount >= max_attempsts_value)) || attempts == 'over' ) {
                // get sitekey
                $("#gatePreviewCaptcha").removeClass('hide');
                is_captcha = 1;
                var sitekey = document.getElementById("captchalog").getAttribute("data-sitekey"); 
                grecaptcha.render('html_element', {
                'sitekey' : sitekey,
                });
            }

             }, 3000);

          });
      }else if(attempts == 'over' ) {

        $( "#overlay-modal-box" ).on('shown.bs.modal', function (e) {
            setTimeout(function(){
                // get sitekey
                $("#gatePreviewCaptcha").removeClass('hide');
                is_captcha = 1;
                var sitekey = document.getElementById("captchalog").getAttribute("data-sitekey"); 
                grecaptcha.render('html_element', {
                'sitekey' : sitekey,
                });

             }, 2000);

          });
      }


  });


function runEmailVerification() {

    var email_address = $("#email_address").val().trim();
    var email_name    = '';
    if($("#email_name").length) {
       email_name    = $("#email_name").val().trim();
    }

    var adcode = '';
    if($("#adcode").length) {
        adcode    = $("#adcode").val().trim();
    }
    var hypesource = '';
    if($("#hypesource").length) {
        hypesource    = $("#hypesource").val().trim();
    }

    var fan_gate_id   = $("#fan_gate_id").val();

    /* HYPE-109 Revert back */
    if (validateEmail(email_address)) {

        var postData = { validateEmailAddress: email_address, fan_gate_id: fan_gate_id,email_name:email_name,adcode:adcode,hypesource:hypesource };

        if (is_captcha == 1) {

            var v = grecaptcha.getResponse();
            if (v.length == 0) {
                $("#gatePreviewCaptcha").removeClass('hide');
                $('#html_element').addClass('form-relative has-error');
                $('#error-captcha').remove();
                $('#html_element').append("<div id='error-captcha' class='name_error_email error-msg' style='display: block;'>Please verify that you are not a robot.</div>");
                return false;
            } else {

               $('#error-captcha').remove();

                $.ajax({
                    type: "POST",
                    url: '/verifyEmailAddress',
                    dataType: "json",
                    data: postData,
                    beforeSend: function() {
                        // setting a timeout
                        $("#email_to_downloads_next").addClass('hy-loading-btn');//.removeClass('hy-btn-lightblue');
                        $("#modal_close_button_text").addClass('hy-loading-btn');//.removeClass('hy-btn-lightblue');
                    },
                    success: function(res) {
                        ////console.log(res);

                        if (res.status === 'T') {
                            // H-1256
                            if (typeof openNewSmartLink == 'function') { 
                              openNewSmartLink(res.eventID); 
                            }
                            // 
                            $("#download_email_address").val(email_address);
                            $("#download_email_step_hide_heading").removeClass('hide')

                            var fangate_style = $('#fangate_style').val();
                            if(fangate_style == 'new'){
                              
                              gateEmailVerificationNextSlide();
                            }else{
                              $("#myCarousel").carousel('next');
                            }                            
                        } else {

                            $(".name_error_email").hasClass('hype-invalid-feedback') 
                                ? $(".name_error_email").html(warningIcon + "Please enter a valid email address.").show().parent().addClass('is-invalid')
                                : $(".name_error_email").html("Please enter a valid email address.").show().parent().addClass('has-error');

                            //$("#email_to_downloads_next").addClass('hy-btn-lightblue').removeClass('hy-btn-orange').removeClass('hy-loading-btn');
                            $("#email_to_downloads_next").removeClass('hy-btn-orange').removeClass('hy-loading-btn');
                            $("#modal_close_button_text").removeClass('hy-btn-orange').removeClass('hy-loading-btn');
                        }
                    }
                });

            }



        } else {

            $.ajax({
                type: "POST",
                url: '/verifyEmailAddress',
                dataType: "json",
                data: postData,
                beforeSend: function() {
                    // setting a timeout
                    $("#email_to_downloads_next").addClass('hy-loading-btn');//.removeClass('hy-btn-lightblue');
                    $("#modal_close_button_text").addClass('hy-loading-btn');//.removeClass('hy-btn-lightblue');
                },
                success: function(res) {
                    ////console.log(res);
               

                    if (res.status === 'T') {
                        if (typeof openNewSmartLink == 'function') { 
                          openNewSmartLink(res.eventID); 
                        }
                        //$("#email_to_downloads_next").addClass('hy-btn-orange').removeClass('hy-btn-lightblue').removeClass('hy-loading-btn');
                        $("#email_to_downloads_next").addClass('hy-btn-orange').removeClass('hy-loading-btn');
                        $("#modal_close_button_text").removeClass('hy-loading-btn');
                        $("#download_email_address").val(email_address);
                        $("#download_email_step_hide_heading").removeClass('hide');

                        var fangate_style = $('#fangate_style').val();
                        if(fangate_style == 'new'){
                            gateEmailVerificationNextSlide();
                        }else{
                            $("#myCarousel").carousel('next');
                        }
                    } else {

                        $(".name_error_email").hasClass('hype-invalid-feedback') 
                            ? $(".name_error_email").html(warningIcon + "Please enter a valid email address.").show().parent().addClass('is-invalid')
                            : $(".name_error_email").html("Please enter a valid email address.").show().parent().addClass('has-error');

                        $("#email_to_downloads_next").removeClass('hy-btn-orange').removeClass('hy-loading-btn');
                        $("#modal_close_button_text").removeClass('hy-loading-btn');
                    }
                }
            });

        }

        /* HYPE-109 Revert back */
    } else {
        $(".name_error_email").show();
        $(".name_error_email").html('Please enter a valid email address.').parent().addClass('has-error');
        $("#loader").hide();
        grecaptcha.reset();
    }

}

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