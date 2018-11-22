/*
Some utilities that we'll be using
 */

function createCookie(name,value,milliseconds) {
    if (milliseconds) {
        var date = new Date();
        date.setTime(date.getTime()+ milliseconds);
        var expires = "; expires="+date.toGMTString();
    }
    else
        var expires = "";

    document.cookie = name+"="+value+expires+"; path=/";
}

function readCookie(name) {
    var nameEQ = name + "=";
    var ca = document.cookie.split(';');
    for(let i=0;i < ca.length;i++) {
        let c = ca[i];
        while (c.charAt(0)==' ')
            c = c.substring(1,c.length);
        if (c.indexOf(nameEQ) == 0)
           return c.substring(nameEQ.length,c.length);
    }
    return null;
}

function eraseCookie(name) {
    createCookie(name, '', -1);
}

// Read all the headers for this page. This requires
// that we 're-read' the page. Use the HTTP HEAD method
// so we don't get the content to speed things up
// return a "map" so we can easily lookup the header
// we are interested in
function readHeaders() {
    let req = new XMLHttpRequest();
    req.open('HEAD', document.location, false);
    req.send(null);
    let headers = req.getAllResponseHeaders().toLowerCase();
    let arr = headers.trim().split(/[\r\n]+/);

    // Create a map of header names to values
    let headerMap = {};
    arr.forEach(function (line) {
      let parts = line.split(': ');
      let header = parts.shift();
      let value = parts.join(': ');
      headerMap[header] = value;
    });

    return headerMap;
}

// Determine if the server that sourced this is NGINX
// that'll mean we add the /api prefix
function is_nginx(headers = null) {
    if (headers == null) {
        headers = readHeaders();
    }

    return headers["server"].includes('nginx');
}