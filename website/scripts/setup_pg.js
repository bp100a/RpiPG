// setup the round Slider

/* Not sure what this is for
window.formatter = function (e) {
    return '*' + e.value;
}
*/
$(document).ready(function () {

        let start_angle = 90; // angles expressed CW
        let end_angle = 200;  // ~ 20 degrees below horizontal
        // Range is always 0-100, so the steps
        // is (end-start) / 100
        let steps = (end_angle - start_angle) / 100;
        $("#slider").roundSlider({
            startAngle: start_angle,
            endAngle: end_angle,
            value: "0, 100",
            sliderType: "range",
            radius: 130,
            tooltipFormat: function (e) {
                return parseInt(90 - (e.value * steps)) + String.fromCharCode(176);
            }
        });

    // labels for our sliders
    let declination_stops = document.querySelector('#camera_rotation');
    declination_stops.oninput =function(){
        let declination_value = document.querySelector('#camera_value');
        let total_value = document.querySelector('#total_value');
        let rotation_stops = document.querySelector('#model_rotation');
        let off = declination_stops.offsetWidth / (parseInt(declination_stops.max) - parseInt(declination_stops.min));
        let px = ((declination_stops.valueAsNumber - parseInt(declination_stops.min)) * off) - (declination_value.offsetWidth / 2);
        declination_value.innerHTML = declination_stops.value + ' ' + 'declination steps';
        if (declination_stops.valueAsNumber == parseInt(declination_stops.min) ) {px += off;}
        if (declination_stops.valueAsNumber == parseInt(declination_stops.max) )  {px -= off;}
        declination_value.parentElement.style.left = px + 'px';
        declination_value.parentElement.style.top = declination_stops.offsetHeight*.75 + 'px';

        // Calculate total # of pictures
        let total_pics = declination_stops.value * rotation_stops.value;
        total_value.innerHTML = ' ' + total_pics + ' pictures'
    };
    declination_stops.oninput() // call to initialize the total picture count

    let rotation_stops = document.querySelector('#model_rotation');
    rotation_stops.oninput=function(){
        let declination_stops = document.querySelector('#camera_rotation');
        let total_value = document.querySelector('#total_value');
        let rotation_value = document.querySelector('#rotation_val');
        let off = rotation_stops.offsetWidth / (parseInt(rotation_stops.max) - parseInt(rotation_stops.min));
        let px = ((rotation_stops.valueAsNumber - parseInt(rotation_stops.min)) * off) - (rotation_value.offsetWidth / 2);
        rotation_value.innerHTML = rotation_stops.value + ' ' + 'rotation steps';
        if (rotation_stops.valueAsNumber == parseInt(rotation_stops.min) ) {px += off;}
        if (rotation_stops.valueAsNumber == parseInt(rotation_stops.max) ) {px -= off;}
        rotation_value.parentElement.style.left = px + 'px';
        rotation_value.parentElement.style.top = rotation_stops.offsetHeight*.75 + 'px';

        // Calculate total # of pictures
        let total_pics = declination_stops.value * rotation_stops.value;
        total_value.innerHTML = ' ' + total_pics + ' pictures'
      };

    rotation_stops.oninput(); // call to initialize the total picture count

    // When button clicked, post values to perform scan
    $('#scan').click(function(){
        upload_google_drive_info(); // if we have it, send it up
        let declination_value = document.querySelector("#camera_rotation").value;
        let rotation_value = document.querySelector("#model_rotation").value;
        let declination_values = $("#slider").roundSlider("getValue").split(',');
        let declination_start = declination_values[1];
        let declination_stop = declination_values[0];
        // alert("declination= " + declination_value + "\nrotation=" + rotation_value + "\nstart/stop =" + declination_start + ', ' + declination_stop);
         $.ajax({
             type: "POST",
             dataType: "json",
             contentType: "application/json; charset=utf-8",
             data: JSON.stringify({"declination_steps": declination_value, "rotation_steps": rotation_value, "start": declination_start, "stop": declination_stop}),
             url: "http://" + location.hostname + "/api/scan",
             success: function(data){
             }
         });
    });

    // setup the polling for status
    (function() {
        poll = function() {
          $.ajax({
            url: "http://" + location.hostname + "/api/status",
            dataType: 'json',
            type: 'get',
            success: function(data) { // check if available
                if (data != null) {
                    let json = JSON.parse(data);
                    console.log(json);
                    if (json.msg) { // get and check data value
                        $('.ticker').append('<li>' + json.msg + '</li>'); // get and print data string
                    }
                }
            },
            error: function() { // error logging
              console.log('Error!');
            }
          });
        },
        pollInterval = setInterval(function() {poll();}, 10000);

        poll(); // also run function on init
    })();

});
