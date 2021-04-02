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


    
    $('form').submit(function() {  
        $('.single-use').attr('disabled', true);
        return true;
        });

    

    history.pushState(null, null, location.href);
    window.onpopstate = function () {
        history.go(1);
        };

        
        
    var date_from_string = function(str){
        var months = ["Jan","Feb","Mar","Apr","May","Jun","Jul", "Aug","Sep","Oct","Nov","Dec"];
        var dateparts = str.split(" ");
        var month = $.inArray(dateparts[1], months);
        return new Date(datetprts[2], month, dateparts[0]);
        }

        
    $('.sortable').
        stupidtable({"date":function(a,b){
          // Get these into date objects for comparison.
          aDate = date_from_string(a);
          bDate = date_from_string(b);
          return aDate - bDate;
        }
      });

        
    });

        
        