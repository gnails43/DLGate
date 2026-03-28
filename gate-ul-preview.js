var arcadegate = $("#gate_ul_preview_js").attr("data-arcadegate");
var arcadegateinline = $("#gate_ul_preview_js").attr("data-arcadegateinline");
var hypesource = $.trim($("#gate_ul_preview_js").data('hypesource'));
var adcode = $.trim($("#gate_ul_preview_js").data('adcode'));
var setarcadeingate = 0;
var inapp = $("#gate_ul_preview_js").attr("data-inapp");
var inappmobile = $("#gate_ul_preview_js").attr("data-inappmobile");
var inappAndroidmobile = $("#gate_ul_preview_js").attr("data-inappAndroidMobile");
var isFacebookApp = /FBMD|FBAV|FBAN|Instagram|musical_ly/i.test(navigator.userAgent);
var isiOSWithoutSafari = (navigator.userAgent.match(/iPhone|iPod|iPad/i) && !navigator.userAgent.match(/Safari/i));
var getArcadeInformationCalled = 0;
var getArcadeInformationCompleted = false;
var downloadonemail = $.trim($("#gate_ul_preview_js").data('downloadonemail'));
var warningIcon = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7.99999 5.83333V8.5M6.85394 2.42744L1.86462 10.8186C1.33616 11.7073 1.97665 12.8333 3.01067 12.8333H12.9893C14.0233 12.8333 14.6638 11.7073 14.1353 10.8186L9.14603 2.42744C8.62921 1.55824 7.37076 1.55824 6.85394 2.42744Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><ellipse cx="7.99992" cy="10.3333" rx="0.666667" ry="0.666667" fill="currentColor"/></svg>';
var gate = {};
$(document).ready(function(){

        sort_steps();

        $('#login_to_sc').on('click', function (e)
        {
            var comment_sc = jQuery("#comment_sc").val();
            if(comment_sc == 1){
                var sc_comment_text = $.trim($("#sc_comment_text").val());
                if ($("#sc_comment_text").val() == '')
                {
                    displayError("sc_comment_error", 'Please enter your comment to get download link.');
                    return false;

                }else{
                    //HYPE-786
                    if ((navigator.userAgent.match(/FBMD/i) || navigator.userAgent.match(/Instagram/i) || navigator.userAgent.match(/Android/i)))
                    {
                        try {
                            var fan_gate_id   =  $("#fan_gate_id").val();
                            $.ajax({
                                type: 'POST',
                                url: '/setSC',
                                async:false,
                                data: {
                                    fan_gate_id :fan_gate_id,
                                    comment_sc: sc_comment_text,
                                },
                                dataType: 'json',
                                beforeSend :function(){
                                },
                                success: function (data){
                                },
                                error: function(XMLHttpRequest, textStatus, errorThrown) {
                                }
                            });
                        } catch (ee) {
                            // console.log('error');
                        }
                    }
                    var theFunc = $(this).attr('data-onclick');
                    eval(theFunc);
                    $("#sc_comment_error").empty().hide().parent().removeClass('has-error');
                    currentSlideCardHeight();
                    return true;
                }
            }
        });
    
        $('#login_to_yt,#ytCarouselSection').on('click', function (e)
        {
            var comment_yt = jQuery("#comment_yt").val();
            if(comment_yt == 1){
                var yt_comment_text = $.trim($("#yt_comment_text").val());
                if ($("#yt_comment_text").val() == '')
                {
                    $("#yt_comment_error").show();
                    $("#yt_comment_error").html('Please enter your comment to get download link.').parent().addClass('has-error');
                    return false;

                }else{
                    //HYPE-786
                    if ((navigator.userAgent.match(/iPhone/i) || navigator.userAgent.match(/iPad/i)) && navigator.userAgent.match(/FBMD/i))
                    {
                        try {
                            var fan_gate_id   =  $("#fan_gate_id").val();
                            $.ajax({
                                type: 'POST',
                                url: '/setYT',
                                data: {
                                    fan_gate_id :fan_gate_id,
                                    comment_yt: yt_comment_text,
                                },
                                dataType: 'json',
                                beforeSend :function(){
                                },
                                success: function (data){
                                },
                                error: function(XMLHttpRequest, textStatus, errorThrown) {
                                }
                            });
                        } catch (ee) {
                           // console.log('error');
                        }
                    }
                    if($(this).hasClass('ytCarouselChecker')) {

                    }else{
                        var theFunc = $(this).attr('data-onclick');
                        eval(theFunc);
                    }
                    $("#yt_comment_error").hide();
                    $("#yt_comment_error").empty().parent()
                    currentSlideCardHeight();
                    return true;
                }
            }
        }) 


        $('#sc_comment_text').keyup(function(){
            var per = $(this);
            var sc_comment_text = $.trim(per.val());
            
            $("#sc_comment_error").html('');

            if (sc_comment_text === '') {
                displayError("sc_comment_error", 'Please enter your comment to get download link.');
                
            } else {
                $("#sc_comment_error").html('').hide().parent().removeClass('has-error');
                currentSlideCardHeight();
            }
        });

        $('#yt_comment_text').keyup(function(){
            var per = $(this);
            var yt_comment_text = $.trim(per.val());
            
            $("#yt_comment_error").html('');

            if (yt_comment_text === '')
            {
                $("#yt_comment_error").html('Please enter your comment to get download link.').show().parent().addClass('has-error');
                
            } else {
                $("#yt_comment_error").html('').hide().parent().removeClass('has-error');
                currentSlideCardHeight();
            }
        });

        // myCarousel 
        $('#myCarousel').find('.item').first().addClass('active');
        $('.carousel-indicators').find('.indicators').first().addClass('active');

        var maxHeight = Math.max.apply(null, $("div.fangate-slider-content").map(function ()
        {
            return $(this).height();
        }).get());
        $('.carousel-inner').height(maxHeight);

        //$('.myCarouselSocialSection').on('click', function(){
        $(document).on('click', ".myCarouselSocialSection", function(){   
            if ($('#myCarousel').length) {
                gateNextSlide(this)
            }
        });

        $('#skipper,#skipper_email,#skipper_yt,#skipper_yt_next,#skipper_sc,#skipper_mc,#skipper_ig,#skipper_ig_next,#skipper_tw,#skipper_fb,#skipper_dn,#skipper_dz,#skipper_ap,#skipper_fbmsgr,#skipper_th,#skipper_tw_next,#skipper_fb_button,#skipper_tk,#skipper_tk_next,#skipper_bc,#skipper_bc_next').on('click', function() {
            var stepName = $(this).data('step');
            if ($('#myCarousel').length) {
                gateNextSlide(this)
            }
            if("sp" == stepName){
                $('#is_skippable').val(1);
            }
            if("email" == stepName){
                $('#download_email_step, #section_download_email_address').removeClass('hide');
                $('#download_email_step_heading').removeClass('hide');
            }
            ////console.log(stepName);
            try {
                $("#skippable_"+stepName).remove();
            } catch (e) {}

            var textBox = '<input type="hidden" id="skippable_'+stepName+'" name="skip_gate_steps[]" value="'+stepName+'">';
            $("#is_skippable").after(textBox);
            //HYPE-786
            
            if ((navigator.userAgent.match(/FBMD/i) || navigator.userAgent.match(/Instagram/i) || navigator.userAgent.match(/Android/i) || navigator.userAgent.match(/Iphone/i) || inapp == true))
            {
                try {
                    var fan_gate_id   =  $("#fan_gate_id").val();
                    $.ajax({
                        type: 'POST',
                        url: '/setGatePathway',
                        data: {
                            fan_gate_id :fan_gate_id,
                            stepName: stepName,
                        },
                        dataType: 'json',
                        beforeSend :function(){
                        },
                        success: function (data){
                        },
                        error: function(XMLHttpRequest, textStatus, errorThrown) {
                        }
                    });
                } catch (ee) {
                    // console.log('error');
                }
            }
        });

        $("#skipper_email").on('click', function() {
            $('#email_address').val('');
            setEmailLinkOrDownloadLink();
        });

        $("#youtube_status a").on('click',function(e) {
            $(".name_error_youtube").hide();
            $(this).removeClass('undone').addClass('done');
            if($("#youtube_status a.undone").length) {

            }else{
                console.log($("#youtube_status a.undone").length);
                $("#skipper_yt_channel").addClass('hide');
                $('#skipper_yt_next').removeClass('hide');
            }
            currentSlideCardHeight();
        });

        $("#skipper_yt_channel").on('click',function(e) {
            if($("#youtube_status a").length && $("#youtube_status a.undone").length) {
                var list_name = ''
                $("#youtube_status a.undone").each(function(i){
                    list_name += $(this).data('title')+", ";
                })
                list_name = list_name.replace(/(^[,\s]+)|([,\s]+$)/g, '').replace(/,(?=[^,]*$)/, ' and');
                
                // var sbMsg = '<p>Oops! It looks like you are not yet subscribed to '+list_name+'</p>';
                var sbMsg = 'Oops! Please subscribe to the artist(s) above on YouTube to continue.';
                $(".name_error_youtube").hasClass('hype-invalid-feedback') 
                    ? $(".name_error_youtube").html(warningIcon + sbMsg).show().parent().addClass('is-invalid-error') 
                    : $(".name_error_youtube").html("<p>" + sbMsg + "</p>").show();

                
            }else{
                $(this).addClass('hide');
                $('#skipper_yt_next').removeClass('hide');
            }
            currentSlideCardHeight();
        })

        $('.youtube_profile').on('click', function (e)
        {
            var ytChannelUrl = $(this).data('ytchannelurl');		
            $("#ytChannelUrl").val(ytChannelUrl);
            
        });

        $("#instagram_status a").on('click',function(e) {
            $(".name_error_instagram").hide();
            $(this).removeClass('undone').addClass('done');
            if($("#instagram_status a.undone").length) {

            }else{
                console.log($("#instagram_status a.undone").length);
                $("#skipper_ig_channel").addClass('hide');
                $('#skipper_ig_next').removeClass('hide');
            }
            currentSlideCardHeight();
        });

        $("#skipper_ig_channel").on('click',function(e) {
            if($("#instagram_status a").length && $("#instagram_status a.undone").length) {
                var list_name = ''
                $("#instagram_status a.undone").each(function(i){
                    list_name += $(this).data('title')+", ";
                })
                list_name = list_name.replace(/(^[,\s]+)|([,\s]+$)/g, '').replace(/,(?=[^,]*$)/, ' and');
                
                var sbMsg = 'Oops! Please follow to the artist(s) above on Instagram to continue.';

                $(".name_error_instagram").hasClass('hype-invalid-feedback') 
                    ? $(".name_error_instagram").html(warningIcon + sbMsg).show().parent().addClass('is-invalid-error') 
                    : $(".name_error_instagram").html("<p>" + sbMsg + "</p>").show();
            }else{
                $(this).addClass('hide');
                $('#skipper_ig_next').removeClass('hide');
            }

            currentSlideCardHeight();
        })

        $("#spotify_public_preview_button").click(function(){
            $("#spotify_public_preview_active").val(1);
        });

        $("#twitter_status a").on('click',function(e) {
            $(".name_error_twitter").hide();
            $(this).removeClass('undone').addClass('done');
            if($("#twitter_status a.undone").length) {

            }else{
                console.log($("#twitter_status a.undone").length);
                $("#skipper_tw_channel").addClass('hide');
                $('#skipper_tw_next').removeClass('hide');
            }
            currentSlideCardHeight();
        });

        $("#skipper_tw_channel").on('click',function(e) {
            if($("#twitter_status a").length && $("#twitter_status a.undone").length) {
                var list_name = ''
                $("#twitter_status a.undone").each(function(i){
                    list_name += $(this).data('title')+", ";
                })
                list_name = list_name.replace(/(^[,\s]+)|([,\s]+$)/g, '').replace(/,(?=[^,]*$)/, ' and');
                
                // var sbMsg = '<p>Oops! It looks like you are not yet subscribed to '+list_name+'</p>';
                var sbMsg = 'Oops! Please support the artist(s) on Twitter with the steps above to continue.';
                $(".name_error_twitter").hasClass('hype-invalid-feedback') 
                    ? $(".name_error_twitter").html(warningIcon + sbMsg).show().parent().addClass('is-invalid-error') 
                    : $(".name_error_twitter").html("<p>" + sbMsg + "</p>").show();

                
            }else{
                $(this).addClass('hide');
                $('#skipper_tw_next').removeClass('hide');
            }
            currentSlideCardHeight();
        })

        $("#facebook_status a").on('click',function(e) {
            $(".name_error_facebook").hide();
            $(this).removeClass('undone').addClass('done');
            if($("#facebook_status a.undone").length) {

            }else{
                console.log($("#facebook_status a.undone").length);
                $("#skipper_fb_like").addClass('hide');
                $('#skipper_fb').removeClass('hide');
            }
            currentSlideCardHeight();
        });

        $("#skipper_fb_like").on('click',function(e) {
            if($("#facebook_status a").length && $("#facebook_status a.undone").length) {
                var list_name = ''
                $("#facebook_status a.undone").each(function(i){
                    list_name += $(this).data('title')+", ";
                })
                list_name = list_name.replace(/(^[,\s]+)|([,\s]+$)/g, '').replace(/,(?=[^,]*$)/, ' and');
                
                // var sbMsg = '<p>Oops! It looks like you are not yet subscribed to '+list_name+'</p>';
                var sbMsg = 'Oops! Please support the artist(s) on Facebook with the steps above to continue.';
                $(".name_error_facebook").hasClass('hype-invalid-feedback') 
                    ? $(".name_error_facebook").html(warningIcon + sbMsg).show().parent().addClass('is-invalid-error') 
                    : $(".name_error_facebook").html("<p>" + sbMsg + "</p>").show();

                
            }else{
                $(this).addClass('hide');
                $('#skipper_fb').removeClass('hide');
            }
            currentSlideCardHeight();
        })


        $("#tiktok_status a").on('click',function(e) {
            $(".name_error_tiktok").hide();
            $(this).removeClass('undone').addClass('done');
            if($("#tiktok_status a.undone").length) {

            }else{
                console.log($("#tiktok_status a.undone").length);
                $("#skipper_tk_channel").addClass('hide');
                $('#skipper_tk_next').removeClass('hide');
            }
            currentSlideCardHeight();
        });

        $("#skipper_tk_channel").on('click',function(e) {
            if($("#tiktok_status a").length && $("#tiktok_status a.undone").length) {
                var list_name = ''
                $("#tiktok_status a.undone").each(function(i){
                    list_name += $(this).data('title')+", ";
                })
                list_name = list_name.replace(/(^[,\s]+)|([,\s]+$)/g, '').replace(/,(?=[^,]*$)/, ' and');
                
                // var sbMsg = '<p>Oops! It looks like you are not yet subscribed to '+list_name+'</p>';
                var sbMsg = 'Oops! Please support the artist(s) on TikTok with the steps above to continue.';

                $(".name_error_tiktok").hasClass('hype-invalid-feedback') 
                    ? $(".name_error_tiktok").html(warningIcon + sbMsg).show().parent().addClass('is-invalid-error') 
                    : $(".name_error_tiktok").html("<p>" + sbMsg + "</p>").show();

                
            }else{
                $(this).addClass('hide');
                $('#skipper_tk_next').removeClass('hide');
            }
            currentSlideCardHeight();
        })

        $("#bandcamp_status a").on('click',function(e) {
            $(".name_error_bandcamp").hide();
            $(this).removeClass('undone').addClass('done');
            if($("#bandcamp_status a.undone").length) {

            }else{
                console.log($("#bandcamp_status a.undone").length);
                $("#skipper_bc_channel").addClass('hide');
                $('#skipper_bc_next').removeClass('hide');
            }
            currentSlideCardHeight();
        });

        $("#skipper_bc_channel").on('click',function(e) {
            if($("#bandcamp_status a").length && $("#bandcamp_status a.undone").length) {
                var list_name = ''
                $("#bandcamp_status a.undone").each(function(i){
                    list_name += $(this).data('title')+", ";
                })
                list_name = list_name.replace(/(^[,\s]+)|([,\s]+$)/g, '').replace(/,(?=[^,]*$)/, ' and');
                
                // var sbMsg = '<p>Oops! It looks like you are not yet subscribed to '+list_name+'</p>';
                var sbMsg = 'Oops! Please support the artist(s) on Bandcamp with the steps above to continue.';

                $(".name_error_bandcamp").hasClass('hype-invalid-feedback') 
                    ? $(".name_error_bandcamp").html(warningIcon + sbMsg).show().parent().addClass('is-invalid-error') 
                    : $(".name_error_bandcamp").html("<p>" + sbMsg + "</p>").show();
            }else{
                $(this).addClass('hide');
                $('#skipper_bc_next').removeClass('hide');
            }
            currentSlideCardHeight();
        })

        $("#twitch_status a").on('click',function(e) {
            $(".name_error_twitch").hide();
            $(this).removeClass('undone').addClass('done');
            if($("#twitch_status a.undone").length) {

            }else{
                console.log($("#twitch_status a.undone").length);
                $("#skipper_th_channel").addClass('hide');
                $('#skipper_th_next').removeClass('hide');
            }
            currentSlideCardHeight();
        });

        $("#skipper_th_channel").on('click',function(e) {
            if($("#twitch_status a").length && $("#twitch_status a.undone").length) {
                var list_name = ''
                $("#twitch_status a.undone").each(function(i){
                    list_name += $(this).data('title')+", ";
                })
                list_name = list_name.replace(/(^[,\s]+)|([,\s]+$)/g, '').replace(/,(?=[^,]*$)/, ' and');
                
                // var sbMsg = '<p>Oops! It looks like you are not yet subscribed to '+list_name+'</p>';
                var sbMsg = 'Oops! Please support the artist(s) on Twitch with the steps above to continue.';

                $(".name_error_twitch").hasClass('hype-invalid-feedback') 
                    ? $(".name_error_twitch").html(warningIcon + sbMsg).show().parent().addClass('is-invalid-error') 
                    : $(".name_error_twitch").html("<p>" + sbMsg + "</p>").show();

                
            }else{
                $(this).addClass('hide');
                $('#skipper_th_next').removeClass('hide');
            }
            currentSlideCardHeight();
        })

        // HYPE-1145 dynamic steps 
        try {
            if (getCookieHype("an", "gtm_visit") == "yes") {
                dataLayer.push({
                    'event': 'gate_visit',
                    'eventCategory': 'Gate',
                    'eventAction': 'Visit',
                    'gateConfiguration':step_array
                });
            }
        } catch (egtm) {
            console.log(egtm);
        }

        $(".optOutOption").click(function() {
            var type = $(this).data('type');
            if (type == 'spotify') {
                $("#optInSectionSpotify").addClass('hide');
                $("#optOutSectionSpotify").removeClass('hide');
                $("#lifetime_fan_sp").val(0);
            }

            if (type == 'deezer') {
                $("#optInSectionDeezer").addClass('hide');
                $("#optOutSectionDeezer").removeClass('hide');
                $("#lifetime_fan_dz").val(0);
            }

            if (type == 'apple') {
                $("#optInSectionApple").addClass('hide');
                $("#optOutSectionApple").removeClass('hide');
                $("#lifetime_fan_ap").val(0);
            }

            currentSlideCardHeight();
        });

        $(".optInOption").click(function() {
            var type = $(this).data('type');
            if (type == 'spotify') {
                $("#optInSectionSpotify").removeClass('hide');
                $("#optOutSectionSpotify").addClass('hide');
                $("#lifetime_fan_sp").val(1);
            }
            if (type == 'deezer') {
                $("#optInSectionDeezer").removeClass('hide');
                $("#optOutSectionDeezer").addClass('hide');
                $("#lifetime_fan_dz").val(1);
            }

            if (type == 'apple') {
                $("#optInSectionApple").removeClass('hide');
                $("#optOutSectionApple").addClass('hide');
                $("#lifetime_fan_ap").val(1);
            }

            currentSlideCardHeight();
        })
});

function trackSpotifyPlaying() {
    var trackId = $("#play_in_sp").data('trackid');
    var refreshId;
    var refreshTimeout ;
    var max_attamp = 3;
    var current_attamp = 0;
    setTimeout(function(){ 
        // $("#close_button_spotify_public_preview").removeClass('button-secondary').addClass('button-primary').attr('data-dismiss','modal'); 
            // clearInterval(refreshId);
            $("#spotify_public_preview_frame").attr('src','');
            gateNextSlide($("#login_to_sp"));
    }, 30000);
    try {

        // // refreshTimeout = setTimeout(function(){ 
            refreshId = setInterval(function() {
                if(current_attamp >= max_attamp) {
                    console.log('max_attamp reached');
                    clearInterval(refreshId);
                    return;
                }
                current_attamp++;
                console.log('current_attamp ' + current_attamp);
                $.ajax({
                    type: 'POST',
                    url: '/check_sp_user_playback',
                    data: {
                        track_id :trackId,
                    },
                    dataType: 'json',
                    beforeSend :function(){
                    },
                    success: function (data){
                        if(data.is_playing == true && data.id == trackId) {
                            console.log('same track is playing');
                            clearInterval(refreshId);
                        }
                    },
                    error: function(XMLHttpRequest, textStatus, errorThrown) {
                        // console.log('error found');
                        clearInterval(refreshId);
                    }
                });
            }, 10000);
        // // }, 10000);
        
    } catch (ee) {
        clearInterval(refreshId);
    }

}

// toggles for the sections in Gate Steps
function sort_steps() {
    var step_wrapper = $('#all_steps');
    step_wrapper.find('.fangate-slider-content').sort(function (a, b) {
            return +a.getAttribute('data-sort') - +b.getAttribute('data-sort');
        })
        .appendTo(step_wrapper);
}

$('#gateDownloadButton, #download_email_button').on('click', function() {
    var type = $(this).data('type');

    if (! type) {
        type = 'gate';
    }

    try {
        getArcadeInformation();
    } catch (err) {}

    var email           = $.trim($('#email_address').val());
    var is_mobile       = $.trim($('#is_mobile').val());
    var mobile_type     = $.trim($('#mobile_type').val());
    
    //HYPE-786
    if ((navigator.userAgent.match(/iPhone/i) || navigator.userAgent.match(/iPad/i)) && navigator.userAgent.match(/FBMD/i))
    {
        try {
            var fan_gate_id   =  $("#fan_gate_id").val();
            $.ajax({
                type: 'POST',
                url: '/getEmail',
                data: {
                    fan_gate_id :fan_gate_id,
                },
                dataType: 'json',
                async:false,
                success: function (res){
                    if (res.action == 1) {
                        email = res.email
                    }
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                }
            });
        } catch (ee) {
            // console.log('error');
        }
    }
    
    var download_action = "DOWNLOAD";
    $("#error_download_email_address").html('').hide();
    if($('#download_email_address').length && type == 'email') {
        email = $.trim($('#download_email_address').val());
        if(email == ''){
            if($("#download_email_step").hasClass('hide')) {
                $("#download_email_step, #section_download_email_address").removeClass('hide');
                return false;    
            }
            displayError("error_download_email_address", 'Please enter your email.');
            return false;
            
        }else if (!validateEmail(email))
        {
            displayError("error_download_email_address", 'Please enter a valid email address.');
            return false;
        }
        download_action = "EMAIL";
    }else if(type == 'linkGate') {
        download_action = "LINK_GATE";
    }
    //
    var curr_section = $("#section-ten");
    if (curr_section.hasClass('upcomming-slide')) {
        return false;
    }
    //
    var gate_type = jQuery("#gate_type").val();
    var wrndk = jQuery("#wrndk").val();
    // soundcloud duration
    var downloadlink = jQuery("#current_download_file_listner").val();
    var duration = jQuery("#duration").val();
    //
    if ((duration == 0) || (duration == '') || (duration == 'undefined') || (duration == 'null') || (duration == null) || (duration == '0')) {
        duration = 3 * 60 * 1000; //default to 3 minutes
    }
    //
    var commment_timestamp1 = Math.floor(Math.random() * duration) + 0;
    //////console.log('time: '+commment_timestamp1+' duration: ' + duration);
    var comment_sc = jQuery("#comment_sc").val();
    if(comment_sc == 1){
        var sc_comment_text = $.trim($("#sc_comment_text").val());
        
        //HYPE-786
        // if ((navigator.userAgent.match(/iPhone/i) || navigator.userAgent.match(/iPad/i)) && navigator.userAgent.match(/FBMD/i))
        if ((navigator.userAgent.match(/FBMD/i) || navigator.userAgent.match(/Instagram/i) || navigator.userAgent.match(/Android/i) || inapp == true))
        {
            try {
                var fan_gate_id   =  $("#fan_gate_id").val();
                $.ajax({
                    type: 'POST',
                    url: '/getSC',
                    data: {
                        fan_gate_id :fan_gate_id,
                    },
                    dataType: 'json',
                    async:false,
                    success: function (res){
                        if (res.action == 1) {
                            sc_comment_text = res.sc_comment_text
                        }
                    },
                    error: function(XMLHttpRequest, textStatus, errorThrown) {
                    }
                });
            } catch (ee) {
                // console.log('error');
            }
        }
        if ($("#sc_comment_text").val() == '')
        {
            displayError("sc_comment_error", 'Please enter your comment to get download link.');
        }
    }
    var comment_yt = jQuery("#comment_yt").val();
    if(comment_yt == 1){
        var yt_comment_text = $.trim($("#yt_comment_text").val());
        
        //HYPE-786
        if ((navigator.userAgent.match(/iPhone/i) || navigator.userAgent.match(/iPad/i)) && navigator.userAgent.match(/FBMD/i))
        {
            try {
                var fan_gate_id   =  $("#fan_gate_id").val();
                $.ajax({
                    type: 'POST',
                    url: '/getYT',
                    data: {
                        fan_gate_id :fan_gate_id,
                    },
                    dataType: 'json',
                    async:false,
                    success: function (res){
                        if (res.action == 1) {
                            yt_comment_text = res.yt_comment_text
                        }
                    },
                    error: function(XMLHttpRequest, textStatus, errorThrown) {
                    }
                });
            } catch (ee) {
                // console.log('error');
            }
        }

        if ($("#yt_comment_text").val() == '')
        {
            $("#yt_comment_error").show();
            $("#yt_comment_error").html('Please enter your comment to get download link.').parent().addClass('has-error');
            // return false;
        }
    }
    //
    var additional_sc_array = new Array();
    $('input[name="additional_sc_user_id[]"]').each(function() {
        additional_sc_array.push($(this).val());
    });
    var additional_yt_array = new Array();
    $('input[name="additional_yt_user_id[]"]').each(function() {
        additional_yt_array.push($(this).val());
    });
    var additional_sp_array = new Array();
    $('input[name="additional_sp_user_id[]"]').each(function() {
        additional_sp_array.push($(this).val());
    });
    var additional_mc_array = new Array();
    $('input[name="additional_mc_user_id[]"]').each(function() {
        additional_mc_array.push($(this).val());
    });
    var social_twitter_array = new Array();
    $('input[name="additional_tw_user_id[]"]').each(function() {
        social_twitter_array.push($(this).val());
    });
    var social_instagram_array = new Array();
    $('input[name="additional_ig_user_id[]"]').each(function() {
        social_instagram_array.push($(this).val());
    });
    var additional_dz_array = new Array();
    var additional_dz_type_array = new Array();
    $('input[name="additional_dz_user_id[]"]').each(function() {
        additional_dz_array.push($(this).val());
        additional_dz_type_array.push($(this).data('profile_type'));
    });

    var additional_ap_array = new Array();
    var additional_ap_type_array = new Array();
    $('input[name="additional_ap_user_id[]"]').each(function() {
        additional_ap_array.push($(this).val());
        additional_ap_type_array.push($(this).data('profile_type'));
    });

    var additional_th_array = new Array();
    var additional_th_type_array = new Array();
    $('input[name="additional_th_user_id[]"]').each(function() {
        additional_th_array.push($(this).val());
        additional_th_type_array.push($(this).data('profile_type'));
    });
    
    var fangate_style = jQuery("#fangate_style").val();
    var is_skippable = jQuery("#is_skippable").val();
    var steps = jQuery("#nwSteps").val();
    var track_id = '';
    var AjaxURL = '/gate/download/ul';
    // 
    var skip_gate_steps = new Array();
    $('input[name="skip_gate_steps[]"]').each(function() {
        skip_gate_steps.push($(this).val());
    });

    var lifetime_fan_spotify = $("#lifetime_fan_sp").val();
    var lifetime_fan_deezer = $("#lifetime_fan_dz").val();
    var lifetime_fan_apple = $("#lifetime_fan_ap").val();

    //HYPE-786
    if ((navigator.userAgent.match(/FBMD/i) || navigator.userAgent.match(/Instagram/i) || navigator.userAgent.match(/Android/i) || (navigator.userAgent.match(/iPhone/i)) || inapp == true))
    {
        try {
            var fan_gate_id   =  $("#fan_gate_id").val();
            $.ajax({
                type: 'POST',
                url: '/getGatePathway',
                data: {
                    fan_gate_id :fan_gate_id,
                },
                dataType: 'json',
                async:false,
                success: function (res){
                    if (res.action == 1) {
                        skip_gate_steps = res.skip_gate_steps;
                    }
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                }
            });
        } catch (ee) {
            // console.log('error');
        }
    }
    //
    $('.top_100').removeClass('disable hy-btn-lightgray disabled');
    $('.free_dwln,.email_free_dwln').addClass('disable hy-btn-lightgray disabled');
    $('#download_email_address').addClass('disable').addClass('disabled');

    var postData = {
        file: encodeURIComponent(downloadlink),
        download_visit: 'true',
        profile_downloads: 'true',
        time: commment_timestamp1,
        sc_comment_text: sc_comment_text,
        yt_comment_text: yt_comment_text,
        page: 'nonsingle',
        additional_sc_user_id : additional_sc_array,
        additional_yt_user_id : additional_yt_array,
        additional_sp_user_id : additional_sp_array,
        additional_dz_user_id : additional_dz_array,
        additional_dz_type_array : additional_dz_type_array,
        additional_mc_user_id : additional_mc_array,
        additional_tw_user_id : social_twitter_array,
        additional_ig_user_id : social_instagram_array,
        is_skippable:is_skippable,
        steps:steps,
        email:email,
        download_action:download_action,
        skip_gate_steps:skip_gate_steps,
        wrndk:wrndk,
        is_mobile:is_mobile,
        additional_ap_user_id : additional_ap_array,
        additional_ap_type_array : additional_ap_type_array,
        additional_th_user_id : additional_th_array,
        additional_th_type_array : additional_th_type_array,
        external_id:jsonGateData['externID'],
        hypesource:hypesource,
        adcode:adcode,
        lifetime_fan_spotify : lifetime_fan_spotify,
        lifetime_fan_deezer : lifetime_fan_deezer,
        lifetime_fan_apple : lifetime_fan_apple,
    };

    $.ajax({
        type: "POST",
        url: AjaxURL,
        dataType: "json",
        data: postData,
        success: function(res) {
            try {
              cookieInAppDelete();
            }
            catch(err) {}
            if(res.download_status) {
                if (getCookieHype("tr", "pixel") == "yes") {
                    try {
                        var custom_facebook_pixel = document.getElementById("gate_ul_preview_js").getAttribute("data-customfbp");
                        var customid = document.getElementById("gate_ul_preview_js").getAttribute("data-customid");
                        if ((custom_facebook_pixel != '')&&(custom_facebook_pixel != '0')) {
                            //
                            fbq('init', custom_facebook_pixel,{external_id: jsonGateData['externID']});
                            //
                        }
                        if(type == 'linkGate') {
                            fbq('trackCustom', 'Hypeddit Link Gate Unlock', {
                            artist_name : jsonGateData['artist_name'],
                            title : jsonGateData['title'],
                            },{eventID: res.event_id});
                        }else{

                            fbq('trackCustom', 'Hypeddit Download', {
                                artist_name : jsonGateData['artist_name'],
                                title : jsonGateData['title'],
                                genre : jsonGateData['genre'],
                            },{eventID: res.event_id});

                        } 
                        //
                    } catch(e) {
                    }
                    if(jsonGateData['google_pixel'] && jsonGateData['google_pixel_label']){
                        // trigger when download 
                        gtag_report_conversion();     
                    }
                    if(jsonGateData['tiktok_pixel']){
                        if(type == 'linkGate') {
                            name = 'Hypeddit Link Gate Unlock';
                        }else{
                            name = 'Hypeddit Download';
                        }
                        var data = [{
                                    content_type:'product',
                                    content_name:name,
                                    content_id  :res.event_id
                                }];
                        ttq.track('Download',{contents:data},{event_id:res.event_id});
                    }
                    if(jsonGateData['snapchat_pixel']) {
                        try {
                        //
                        snapchat_event_name = 'SAVE';
                        snapchat_event_tag = 'Download';
                        snaptr('track', snapchat_event_name, {'event_name':snapchat_event_name, 'event_tag':snapchat_event_tag, 'event_id':res.event_id, 'client_dedup_id':res.event_id});
                        } catch(e) {
                            console.log(e.message);
                        }
                    }
                }
            }
            // 
            if(res.download_status && download_action == "LINK_GATE") {
                if (res.custom_redirection_url != '') {
                        setTimeout(function () {
                            if ($.cookie("filedownloading")) {
                                $.removeCookie("filedownloading");
                            }
                            location.href = res.custom_redirection_url;
                        }, 3000);
                }
            }else if(res.download_status && download_action == "EMAIL")
            {
                $("#msg_download_email_address, #hype_msg_download_email_address").text('Download sent to '+email).removeClass('hide');
                $("#download_email_step_heading").addClass('hide').attr("style", "display: none !important");
                $("#download_email_step_hide_heading").addClass('hide');
                if ((res.from_exchange == "1") || (res.from_exchange == "2") || (res.from_exchange == "3")) {
                    setTimeout(function() {
                        location.href = "/exchange";
                    }, 3000);
                }else if (res.arcade_in_gate == 1) {

                    var passGenreSlug = 0;
                    if (res.genre_slug != '') {
                        passGenreSlug = res.genre_slug;
                    }

                    var tryGetArcadeCount = 0;
                    if (getArcadeInformationCompleted == true) {
                            triggerArcadeGate(passGenreSlug);
                    } else {
                        while(getArcadeInformationCompleted == false && tryGetArcadeCount <= 3) {

                            tryGetArcadeCount = tryGetArcadeCount + 1;

                            setTimeout(function () {
                                if (getArcadeInformationCompleted == true) {
                                    triggerArcadeGate(passGenreSlug);
                                    getArcadeInformationCompleted = false;
                                }
                            }, 2000);
                        }
                    }

                    if (res.arcade_download_modal == 1) {
                        $('#download-link-sent').modal({show: 'true', backdrop: 'static', keyboard: false});
                    }
                
                }
                return false;
            }
            else if (res.download_status && res.URL && res.URL !== '') {

                $('#loader_create').hide();
                var targetUrl = res.URL;
    
                if (targetUrl.includes('hypeddit')) {
                    window.location.assign(targetUrl);
                } else {
                    console.error("Blocked unauthorized redirect to: " + targetUrl);
                }
                // window.location.assign(res.URL);
                //
                // if coming from exchange
                if ((res.from_exchange == "1") || (res.from_exchange == "2") || (res.from_exchange == "3")) {
                    setTimeout(function () {
                        if ($.cookie("filedownloading")) {
                            $.removeCookie("filedownloading");
                            location.href = "/exchange";
                        }
                    }, 3000);
                } else if (res.custom_redirection_url != '') {
                    setTimeout(function () {
                        if ($.cookie("filedownloading")) {
                            $.removeCookie("filedownloading");
                            location.href = res.custom_redirection_url;
                        }
                    }, 3000);
                } else if (res.arcade_redirect && parseInt(res.arcade_redirect) == 1) {
                    //
                    if (res.arcade_in_gate == 1) {

                        var passGenreSlug = 0;
                        if (res.genre_slug != '') {
                            passGenreSlug = res.genre_slug;
                        }

                        var tryGetArcadeCount = 0;
                        if (getArcadeInformationCompleted == true) {
                            triggerArcadeGate(passGenreSlug);
                        } else {
                            while(getArcadeInformationCompleted == false && tryGetArcadeCount <= 3) {

                                tryGetArcadeCount = tryGetArcadeCount + 1;

                                setTimeout(function () {
                                    if (getArcadeInformationCompleted == true) {
                                        triggerArcadeGate(passGenreSlug);
                                        getArcadeInformationCompleted = false;
                                    }
                                }, 2000);
                            }
                        }

                        if (res.arcade_download_modal == 1) {
                            if(is_mobile) {
                                $("#download-started-text").text('Once it’s done, you can access the files directly on your device (often in the downloads folder).')
                            }
                            $('#download-started').modal({show: 'true', backdrop: 'static', keyboard: false});
                        }
                    } else {

                        setTimeout(function () {
                            if ($.cookie("filedownloading")) {
                                $.removeCookie("filedownloading");
                                // location.href = "/hot-or-not";
                                if (res.genre_slug != '') {
                                    location.href = "/hot-or-not/" + res.genre_slug + '?refer_source=track_download';
                                } else {
                                    location.href = "/hot-or-not?refer_source=track_download";
                                }
                            }
                        }, 3000);
                    }
                } else if ((res.plan_id && parseInt(res.plan_id) < 2) || (res.always_music && parseInt(res.always_music) == 1)) {
                    setTimeout(function () {
                        if ($.cookie("filedownloading")) {
                            $.removeCookie("filedownloading");
                            if (res.genre_slug != '') {
                                location.href = "/music/genre/" + res.genre_slug + '?refer_source=track_download';
                            } else {
                                location.href = "/music?refer_source=track_download";
                            }
                        }
                    }, 3000);
                }

            } else {
                $('#loader_create').hide();
                return false;
            }
        },
        error: function() {
            $('#loader_create').hide();
            // 
            try {
              cookieInAppDelete();
            }
            catch(err) {}
            // 
            return false;
        }
    });
 
});

function triggerArcadeGate(genre) {

    console.log("triggerArcadeGate:start");
    console.log("triggerArcadeGate:setarcadeingate:" + setarcadeingate);

    try{
        $("#youtubevideoframe, #vimeovideoframe, #wistiavideoframe").detach();
    }catch(errVid){}
    //pause gate player
    if( setarcadeingate === 0 ) {
        if ($(".audiocontrol").hasClass('pause')) {
            $(".player-rt .audiocontrol").click();
        }
        setarcadeingate = 1;
        $(".arcadegate").addClass('hide');
        $(".arcadegate_include").css({
                   "visibility": "visible",
                   "height": "auto",
                   "overflow": "initial",
               });
        $("body").addClass('hot-or-not-page');
        
        var urlsource      = '';
        var fangate_id     = '';
        var fangate_type   = '';
        var selection_type = '';
        var settype        = '';
        var gate_uid       = $("#current_fangate_id").val();
        // 
        var nextPlayer = $("#arcade_list span:first");

        console.log("triggerArcadeGate:getarcadelist");

        if (nextPlayer.length) {
            urlsource      = nextPlayer.data('urlsource');
            fangate_id     = nextPlayer.data('gateid');
            fangate_type   = nextPlayer.data('gatetype');
            settype        = nextPlayer.data('ftype');
            selection_type = nextPlayer.data('selectiontype');
        }
        $.ajax({
            type: "POST",
            url: '/setarcadeingate',
            dataType: "json",
            data: {
                uid:gate_uid, url_source:urlsource,genre:genre,
                fangate_id:fangate_id, fangate_type:fangate_type, 
                selection_type:selection_type, settype:settype 
            },
            success: function(res) {
                var playlist_code = res.playlist_code;
                if (playlist_code!=='') {

                    $('#playlist').attr('href','/playlist/'+playlist_code);
                    // trigger auto play
                    playPlayer();
                    // 
                    try{
                        activePlayController[1000].handleContentResize();
                    }catch(ee){}

                }
            },
            error: function() {
                
                return false;
            }
        });
    }
}

function checkYtManualSubscribed(){
    // code that check if specified youtube channels (in the preview page) are Subscribed or not
}
// HYPE-1113
function inAppSetup(obj,stepCount) {
    try {
        var url = $(obj).data('url');
        var type = $(obj).data('type');
        
        if (
            navigator.userAgent.match(/FBMD/i) || 
            navigator.userAgent.match(/FBAV/i) || 
            navigator.userAgent.match(/FBAN/i) || 
            navigator.userAgent.match(/Mac OS/i) || 
            navigator.userAgent.match(/Android/i) || 
            navigator.userAgent.match(/Instagram/i) ||
            navigator.userAgent.match(/musical_ly/i)
        ) {

            if(type == 'youtube' || type == 'donation' || type == 'instagram' || type == 'facebook' || type == 'twitter' || type == 'tiktok'|| type == 'bandcamp') {

                if (history.pushState) {
                    var nextGroup = $("div[data-group="+stepCount+"]").next('.fangate-slider-content').data('group');
                    if(typeof nextGroup ==  'undefined') {
                        nextGroup = 1000;
                    }
                    var newurl = window.location.origin + window.location.pathname + '?nxstp='+nextGroup;
                    window.history.pushState({path:newurl},'',newurl);
                }

                $("#in_app_msg_close").data('url',url)
                $("#in_app_msg_close").data('type',type)
                if(type == 'youtube') {
                    $("#in_app_msg_txt").text("Please follow/subscribe to the artist on the next page. Then use the BACK button of your browser to return to this page and unlock your download.");
                }

                if(type == 'donation') {
                    $("#in_app_msg_txt").text("Please donate to the artist on the next page. Then use the BACK button of your browser to return to this page and unlock your download.");
                }

                if(type == 'instagram' || type == 'facebook' || type == 'twitter' || type == 'tiktok' || type == 'bandcamp') {
                    $("#in_app_msg_txt").text("Please follow to the artist on the next page. Then use the BACK button of your browser to return to this page and unlock your download.");
                }
                
                $("#in_app_msg").modal({show: 'true', backdrop: 'static', keyboard: false});
            }else {
                setInAppCookie(type);
            }
            try {
                if (type === 'spotify') {
                    inappmobile && $("#dialog-action").removeClass('hide');
                }
            } catch (err) {}
        }
    }catch(err) {}

    currentSlideCardHeight();
}
// 
$("#in_app_msg_close").click(function(){
    var url = $(this).data('url');
    var type = $(this).data('type');
    setInAppCookie(type);
    PopupCenterDual(url,'yt_popup','500','500');
});
// 
function setInAppCookie(type) {
    const date = new Date();
    const uid  = $("#current_fangate_id").val();
    date.setTime(date.getTime() + (5 * 60 * 1000));
    var cookiename = 'inapp_'+uid+'=1; ' + 'expires=' + date.toUTCString() +';path=/';
    // alert('cookie name ' + cookiename);
    document.cookie = 'inapp_'+uid+'=1; ' + 'expires=' + date.toUTCString() +';path=/';
    // document.cookie = 'inapp_step_'+uid+'=' + type + '; ' + 'expires=' + date.toUTCString() +';path=/';
}
// 
function cookieInAppExists() {
    var uid  = $("#current_fangate_id").val();
    var name = 'inapp_'+uid;
    return (document.cookie.split('; ').indexOf(name + '=1') !== -1);
}
// 
function cookieInAppDelete() {
    var uid  = $("#current_fangate_id").val();
    var name = 'inapp_'+uid;
    const date = new Date();
    date.setTime(date.getTime() - (24 * 24 * 60 * 60 * 1000));
    document.cookie = 'inapp_'+uid+'=; ' + 'expires=' + date.toUTCString() +';path=/';
}
// 
function cookieInAppStep() {
    if(cookieInAppExists()) {
        var uid  = $("#current_fangate_id").val();
        var name = 'inapp_step_'+uid;
        return $.cookie(name)
    }else{

        return '';
    }
}

function getArcadeInformation () {

    console.log("getArcadeInformation:arcadegateinline:start: " + arcadegateinline);
    console.log("getArcadeInformation:arcadegate" + arcadegate);
    console.log("getArcadeInformation:getArcadeInformationCalled" + getArcadeInformationCalled);

    if (arcadegateinline == 1) {
        getArcadeInformationCompleted = true;
        return;
    }
    if (arcadegate != 1) {
        getArcadeInformationCompleted = true;
        return;
    }
    if (getArcadeInformationCalled == 1) {
        getArcadeInformationCompleted = true;
        return;
    }

    getArcadeInformationCalled = 1;
    try {
        let $source = $('#arcade_list');
        let urlSource = $source.data('urlsource');
        let genreId = $source.data('genre');
        let genreGroupId = $source.data('genregroup');

        $.ajax({
            type: 'POST',
            url: '/getarcadeinfo',
            data: {url_source: urlSource, filter_genre_id: genreId, filter_genre_group_id: genreGroupId},
            dataType: 'json',
            success: function (data) {

                console.log("getArcadeInformation:getarcadeinfo:returned: " + data.length);

                if (data.length) {
                    $source.html('');
                    for (let i in data) {
                        let track = data[i];
                        let spotlightID = track.spotlight_id ? track.spotlight_id : 0;
                        let arcadeRaw = '<span id="track_'+track.fangate_id+'" data-urlsource="'+urlSource+'" data-selectiontype="'+track.selection_type+'" data-uid="'+track.uid+'" data-gatetype="'+track.type+'" data-buylink="'+track.buylink+'" data-ismusiclink="'+track.is_music_link+'" data-destinationlink="'+track.destination_link+'" data-trackid="'+track.trackid+'" data-permalink="'+track.permalink+'" data-gateid="'+track.fangate_id+'" data-isplaylist="'+track.isplaylist+'" data-ftype="'+track.ftype+'" data-spotlightid="'+spotlightID+'"></span>';
                        $source.append(arcadeRaw);
                    }

                    console.log("getArcadeInformation:getarcadeinfo:completed creating list");

                    var socialDivData = '';
                    var nextPlayer = $("#arcade_list span:first");
                    var gateid = nextPlayer.data('gateid');
                    var spotlightid = nextPlayer.data('spotlightid');
                    var gateType = nextPlayer.data('gatetype');
                    var uid = nextPlayer.data('uid');
                    var trackType = 'tracks';
                    if (nextPlayer.data('isplaylist') == 'true') {
                        trackType = 'playlists';
                    }
                    var trackId = nextPlayer.data('trackid');
                    var permalink = nextPlayer.data('permalink');

                    if (gateType == 'youtube') {
                        if (trackId == '') {
                            var videoId = permalink.match(/(?:https?:\/{2})?(?:w{3}\.)?youtu(?:be)?\.(?:com|be)(?:\/watch\?v=|\/)([^\s&]+)/);
                            trackId = videoId[1];
                        }
                    }
            
                    if (gateType == 'soundcloud' && scusecustomplayer == 0) {
                        trackId = extractSoundcloudId(trackId);

                        socialDivData = '<iframe data-playertype="' + gateType + '" id="player-frame" width="100%" height="100%" scrolling="no" frameborder="no" allow="autoplay" src="https://w.soundcloud.com/player/?url=https%3A//api.soundcloud.com/' + trackType + '/' + trackId + '&amp;color=ff5500&amp;auto_play=false&amp;hide_related=false&amp;visual=true&amp;show_comments=true&amp;show_user=true&amp;show_reposts=false&amp;show_artwork=true&enable_api=true&amp;show_teaser=false" allow="autoplay"></iframe>';
                    }
            
                    if (gateType == 'soundcloud' && scusecustomplayer == 1) {
                        socialDivData = '<div id="frame_'+spCounter+'" data-playertype="' + gateType + '" class="spotlight-player listPlayer HY-wframe" data-counter="'+spCounter+'"  data-uid="'+uid+'" data-auto="true" data-active="active"></div>';
                    }
            
                    if (gateType == 'youtube') {
                        socialDivData = '<iframe data-playertype="' + gateType + '" id="player-frame" width="100%" height="100%" scrolling="no" frameborder="no" src="https://www.youtube.com/embed/' + trackId + '?enablejsapi=1&rel=0&autoplay=0&origin='+APP_URL+'" frameborder="0" allowfullscreen allow="autoplay"></iframe>';
                    }
            
                    if (gateType == 'mixcloud') {
                        socialDivData = '<iframe data-playertype="' + gateType + '" id="player-frame" width="100%" height="300" scrolling="no" frameborder="no" src="https://www.mixcloud.com/widget/iframe/?hide_cover=1&light=1&autoplay=0&feed=' + permalink + '" frameborder="0" allowfullscreen allow="autoplay"></iframe>';
                    }
                    
                    if (gateType == 'spotify' || gateType  == 'unknown') {
                        socialDivData = '<div id="frame_'+spCounter+'" data-playertype="' + gateType + '" class="spotlight-player listPlayer HY-wframe" data-counter="'+spCounter+'"  data-uid="'+uid+'" data-auto="true" data-active="active"></div>';
                    }

                    $(socialDivData).hide().appendTo($('#arcade-player-frame')).fadeIn(800);
                    $("#not-hot-music, #hot-music").attr('data-fangate', gateid).attr('data-spotlight', spotlightid).attr('disabled', true);
                    
                    initPlay = 0;
                    apiSetup = 0;
                    clearAllSetTimeOut();
                    bindPlayer(gateType);
                    try{
                        clearTimerFailsTry = setTimeout(function() {
                            failsTry();
                        }, 3000);
                    }catch(ee){}
                    try{
                    clearTimerNext = setTimeout(function() {
                            enableButton();
                        }, 10000);
                    }catch(ee){}

                    // we will set intial impression here
                    setarcadeimpression();

                    getArcadeInformationCompleted = true;

                    console.log("getArcadeInformation:getarcadeinfo:completed");
                }
            },
            error: function(XMLHttpRequest, textStatus, errorThrown) {
                getArcadeInformationCompleted = true;
                console.log("getArcadeInformation:getarcadeinfo:error");
            }
        });
    } catch(err){ getArcadeInformationCompleted = true; }
}

function setEmailLinkOrDownloadLink () {
    if (downloadonemail == 0) {
        return true;
    }
    var is_mobile = $("#is_mobile").val()
    var mobile_type = $.trim($('#mobile_type').val());
    var email = $.trim($('#email_address').val());

    if (downloadonemail == 1 && (! is_mobile || (is_mobile && mobile_type == 'android' && email == ''))) {
        $("#download_email_step_hide_heading, #gateDownloadButton").removeClass('hide');
        $("#download_email_step_heading, #download_email_step, #download_email_button, #section_download_email_address").addClass('hide');
    }
    currentSlideCardHeight();
}

function displayError(obj, message) {
    if (obj && message) {
        if ($("." + obj).length) {
            $("." + obj).hasClass('hype-invalid-feedback') ? $("." + obj).html(warningIcon + message).show().parent().addClass('is-invalid') : $("." + obj).html(message).show().parent().addClass('has-error');

        } else {
            $("#" + obj).hasClass('hype-invalid-feedback') ? $("#" + obj).html(warningIcon + message).show().parent().addClass('is-invalid') : $("#" + obj).html(message).show().parent().addClass('has-error');
        }
    }
    currentSlideCardHeight();
}

function gateNextSlide (obj) {
    if (! obj) return;

    var indicator  = $('.carousel-indicators .active');
    indicator.toggleClass('active');
    indicator.next('.indicators').toggleClass('active');
    $(obj).parents('.fangate-slider-content').toggleClass('move-left');
    var currentdiv = $(obj).parents('.fangate-slider-content');
    var currentzindex = currentdiv.css("z-index");
    var gate_design_template = $("#gate_design_template").val();

    $(obj).parents('.fangate-slider-content').next().toggleClass('upcomming-slide').css('z-index',parseInt(currentzindex)+1);

    if (gate_design_template == 'modern') {
        currentSlideCardHeight();
    }
}

function currentSlideCardHeight() {
    var gate_design_template = $("#gate_design_template").val();
    if (gate_design_template != 'modern' ) return;
    var currentSlideHeight = $('.fangate-slider-content').not('.move-left').first().height();
    $('.carousel-inner').height(currentSlideHeight);
}

$( window ).resize(function() {
    currentSlideCardHeight();
});

$('#email_to_downloads_next, .hype-invalid-feedback').on('click', function (e) {
    setTimeout(function() {
        currentSlideCardHeight();
    }, 0);
});