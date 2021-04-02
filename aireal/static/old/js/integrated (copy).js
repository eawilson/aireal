$(function () {    
    
    
    
    $('#logout-menu > a').one("click", function (e) {
        $('#logout-menu > div').load($("#logout-menu").attr("data-href"));
        });

    
    
    $('.clickable').
        click( function() {
            window.location = $(this).attr('data-href');
            }).
        hover( function() {
            $(this).toggleClass('hover');
            });

    
    
    $("#save-icon").click(function (e) {
        array = [];
        $(".multi-select > tr")
            .each(function (index, element) {
                array.push($(element).attr("data-pk") + "=" + ($(element).hasClass("selected") ? 1 : 0));
                });
        $("#multi-select-control").val(array.join(","));
        $("#multi-select-form").submit();
        });


    
    $('form').submit(function() {  
        $('.single-use').attr('disabled', true);
        return true;
        });

    
    
    totalCount = parseInt($("#total-count").attr("data-count"));
    totalOutput = parseInt($("#total-output").attr("data-output"));
    $("#total-count").text(totalCount.toString());
    $("#total-output").text((totalOutput/1000).toString());
    
    
    
    function selectRow (element) {
        element = $(element);
        if (element.hasClass("selected") != isSelected) {
            element.toggleClass("selected", isSelected);
            output = parseInt(element.attr("data-output"));
            sign = isSelected ? 1 : -1;
            totalCount = totalCount + sign;
            totalOutput = totalOutput + (output * sign);
            $("#total-count").text(totalCount.toString())
            $("#total-output").text((totalOutput/1000).toString())
            }
        }
    
    
        
    // multiselect table
    var isMouseDown = false,
        isSelected;
    $(".multi-select > tr")
        .mousedown(function (e) {
            if (e.which == 1) {
                isMouseDown = true;
                isSelected = !($(this).hasClass("selected"));
                selectRow(this);
                e.preventDefault(); // prevent text selection
                }
            })
        .mouseover(function () {
            if (isMouseDown) {
                selectRow(this);
                }
            });

    $(document)
        .mouseup(function () {
            isMouseDown = false;
            });

        
        
        
    // contextmenu
//     contextMenu = $(".context-menu");
//     multiSelect = $("#hiway-table").hasClass("multi-select");
//     menuVisible = false;
//     
//     $(document)
//         .contextmenu(function (e) {
//             source = $(e.target).parents().closest(".right-clickable");
//             if (source.length) {
//                 newTop = e.clientY + "px"
//                 newLeft = e.clientX + "px"
//                 contextMenu.css("top", newTop).css("left", newLeft);
//             
//                 if (!source.hasClass("selected")) {
//                     $(".selected").toggleClass("selected", false);
//                     source.toggleClass("selected", true);
//                     }
//                 showMenu();
//                 menuVisible = true;
//                 }
//             else {
//                 hideMenu();
//                 }
//             e.preventDefault();
//             })
//         .click(function (e) {
//             if (e.which == 1) {
//                 hideMenu();
//                 }
//             })
//         .keyup(function (e) {
//             if (e.which == 27) {
//                 hideMenu();
//                 }
//             });
    
    $(window)
        .resize(function (e) {
            hideMenu();
            });        
    });

//     function hideMenu () {
//         if (menuVisible) {
//             if (!multiSelect) {
//                 $(".selected").toggleClass("selected", false);
//                 }
//             contextMenu.toggleClass("context-menu--active", false);
//             menuVisible = false;
//             }
//         }
// 
// 
//     function showMenu () {
//         url = contextMenu.attr("data-href");
//         if (url.length) {
//             array = [];
//             $("#hiway-table > tbody > tr.selected")
//                 .each(function (index, element) {
//                     array.push($(element).attr("data-pk"));
//                     });
//             contextMenu.load(url + "/" + array.join(","), function( response, status, xhr ) {
//                 if ( status != "error" ) {
//                     contextMenu.toggleClass("context-menu--active", true);
//                     }
//                 })
//             }
//         }
        
        
        
        
        