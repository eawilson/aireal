function navigate(href) {
        var url = new URL(href, window.location.href);
        if (url.pathname == "/back") {
            var navstack = JSON.parse(sessionStorage.getItem("navstack"));
            if (navstack === null || !navstack.length) {
                url = new URL("/", window.location.href);
                navstack = [url.href];
                }
            href = navstack[navstack.length - 1];
            }
        window.location.replace(href);
        }


function navigateHandler() {
    const href = $(this).attr("href") || $(this).data("href");
    navigate(href);
    return false;
    }


function defer(func) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', func);
        }
    else {  // `DOMContentLoaded` has already fired
        func();
        }
    }


function openModal(identifier) {
    document.documentElement.classList.add("is-clipped");
    $(identifier).addClass("is-active");
    }


function closeModals() {
    document.documentElement.classList.remove("is-clipped");
    $(".modal").removeClass("is-active");
    }


defer (function() {
    if (document.referrer) {
        var url = new URL(window.location.href);
        var dir = url.searchParams.get("dir");
        var referrer = new URL(document.referrer);
        if (dir && url.pathname != referrer.pathname) {
            var navstack = JSON.parse(sessionStorage.getItem("navstack"));
            if (navstack === null) {
                navstack = [];
                }
            else if (navstack.length > 9) {
                navstack.shift();
                }
            
            if (dir == "1") {
                referrer.searchParams.set("dir", "-1");
                navstack.push(referrer.href);
                }
            else if (dir == "-1") {
                navstack.pop();
                }
            
            sessionStorage.setItem("navstack", JSON.stringify(navstack));
            }
        }
    

    $("a[href]").on("click", navigateHandler);
    
    // Only allow a form to be submitted once. Should have sufficient logic
    // to prevent dara corruption if multiple submissions but this ensures
    // that the response the user sees reflects the first submission.
    $('form').one('submit', function() {
        var navstack = JSON.parse(sessionStorage.getItem("navstack"));
        if (navstack !== null && navstack.length) {
            $(this).children('input[name="back"]').val(navstack[navstack.length - 1]);
            }
        $(this).children('input[type="submit"]').attr('disabled', true);
        return true;
        });


    // Lazy load dropdown menus.
    $('.has-dropdown').one('mouseenter', function() {
        $(this).children('.navbar-dropdown').load($(this).attr('data-href'));
        return true;
        });

    
    // Prevent accidental dragging of elements as looks ugly.
    $('body').on('ondragstart', function() {
        return false;
        });
    
    
    $(".modal-close").on("click", closeModals);
    
    
    $("input").on("invalid", function() {
        $(this).addClass("is-danger");
        });
    
    
    $("input").on("input", function() {
        $(this).removeClass("is-danger");
        });
    
    });



