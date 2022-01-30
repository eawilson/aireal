// function navigate(href) {
//         var url = new URL(href, window.location.href);
//         if (url.pathname == "/back") {
//             var navstack = JSON.parse(sessionStorage.getItem("navstack"));
//             if (navstack === null || !navstack.length) {
//                 url = new URL("/", window.location.href);
//                 navstack = [url.href];
//                 }
//             href = navstack[navstack.length - 1];
//             }
//         window.location.replace(href);
//         }

function navigate(href) {
    window.location.replace(href);
    }



function ajaxGet(url, callback, element) {
    const httpRequest = new XMLHttpRequest();
    
    function checkSuccess() {
        if (httpRequest.readyState === XMLHttpRequest.DONE &&  httpRequest.status === 200) {
            callback(element, httpRequest.responseText);
            }
        }
    
    httpRequest.onreadystatechange = checkSuccess;
    httpRequest.open('GET', url);
    httpRequest.send();
    }


// function defer(func) {
//     if (document.readyState === 'loading') {
//         document.addEventListener('DOMContentLoaded', func);
//         }
//     else {  // `DOMContentLoaded` has already fired
//         func();
//         }
//     }


//defer (function() {
//     if (document.referrer) {
//         var url = new URL(window.location.href);
//         var dir = url.searchParams.get("dir");
//         var referrer = new URL(document.referrer);
//         if (dir && url.pathname != referrer.pathname) {
//             var navstack = JSON.parse(sessionStorage.getItem("navstack"));
//             if (navstack === null) {
//                 navstack = [];
//                 }
//             else if (navstack.length > 9) {
//                 navstack.shift();
//                 }
//             
//             if (dir == "1") {
//                 referrer.searchParams.set("dir", "-1");
//                 navstack.push(referrer.href);
//                 }
//             else if (dir == "-1") {
//                 navstack.pop();
//                 }
//             
//             sessionStorage.setItem("navstack", JSON.stringify(navstack));
//             }
//         }
    
(function() {
    
    function navigateHandler(e) {
        e.preventDefault();
        navigate(e.currentTarget.href);
        }
    
    const anchors = document.querySelectorAll('a[href]');
    for (var i = 0; i < anchors.length; ++i) {
        if (anchors[i].target != '_blank') {
            anchors[i].addEventListener('click', navigateHandler);
            }
        }
    
    
    
    // Lazy load dropdown menus.
    function insertDropdown(element, data) {
        element.querySelector('.navbar-dropdown').innerHTML = data;
        }
        
    function dropdownHandler(e) {
        const target = e.target;
        ajaxGet(target.dataset.href, insertDropdown, target);
        }

    const dropdowns = document.querySelectorAll('.has-dropdown');
    for (var i = 0; i < dropdowns.length; ++i) {
        dropdowns[i].addEventListener('mouseenter', dropdownHandler, {'once': true});
        }



    // Prevent accidental dragging of elements as looks ugly.
    function preventDefault(e) {
        e.preventDefault();
        }
    
    document.body.addEventListener('ondragstart', preventDefault);

    })();



