function jumpGate(obj,type) {
        try{
            var groupNumber = $(obj).data('group');
            var steps = jQuery("#steps_select").val();
            var skip_steps = new Array();
            skip_steps =  steps.split(',');
            var fan_gate_id = jQuery("#fan_gate_id").val();
            if(skip_steps[groupNumber]){
                var skip_or_steps = new Array();
                skip_or_steps   =  skip_steps[groupNumber].split('|');
                var typeIndex = skip_or_steps.indexOf(type);
                if (typeIndex > -1) { 
                    skip_or_steps.splice(typeIndex, 1);
                }

                $.each(skip_or_steps, function( index, value ) {
                    if(value != type){
                        var textBox = '<input type="hidden" id="skippable_'+value+'" name="skip_gate_steps[]" value="'+value+'">';
                        $("#is_skippable").after(textBox);
                    }
                });

                if ((navigator.userAgent.match(/FBMD/i) || navigator.userAgent.match(/Instagram/i) || navigator.userAgent.match(/Android/i) || navigator.userAgent.match(/musical_ly/i) || navigator.userAgent.match(/iPhone/i) || inapp == true)) {
                    try {
                        $.ajax({
                            type: 'POST',
                            url: '/setGatePathwayOr',
                            data: {
                                fan_gate_id :fan_gate_id,
                                skipSteps: skip_or_steps,
                                selectedStep: type
                            },
                            dataType: 'json',
                            success: function (data) { },
                            error: function(XMLHttpRequest, textStatus, errorThrown) { }
                        });
                    } catch (ee) { }
                }
            }
            $(".step_button_"+groupNumber).hide();
            $("#step_"+type).removeClass('hide');

            var maxHeight = Math.max.apply(null, $("div.fangate-slider-content").map(function () {
                return $(this).height();
            }).get());
            $('.carousel-inner').height(maxHeight);
            $(".group_header_"+groupNumber).hide();
            $(".group_header_or_"+groupNumber).hide();
        }catch(ee){
            console.log(ee)
        }

        currentSlideCardHeight();

        if (type == 'fb') {
            setTimeout(function() {
                currentSlideCardHeight();
            }, 300);
        }
    }