$(document).ready(function() {

    setAjaxHeader();
});

function setAjaxHeader()
{
    $.ajaxSetup({
        headers: {
            'X-CSRF-TOKEN': $('meta[name="csrf-token"]').attr('content')
        }
    });
}

function deleteAjaxHeader()
{
    delete $.ajaxSettings.headers["X-CSRF-TOKEN"];
}
