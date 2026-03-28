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