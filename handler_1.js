function (e)
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
    }