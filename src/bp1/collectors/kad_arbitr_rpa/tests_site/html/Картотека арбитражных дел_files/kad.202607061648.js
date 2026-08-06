/* Minification failed. Returning unminified contents.
(1192,67-68): run-time error JS1014: Invalid character: `
(1192,86-87): run-time error JS1193: Expected ',' or ')': {
(1192,93-94): run-time error JS1195: Expected expression: ,
(1192,102-103): run-time error JS1193: Expected ',' or ')': {
(1192,109-110): run-time error JS1002: Syntax error: }
(1192,120-121): run-time error JS1002: Syntax error: }
(1192,133-134): run-time error JS1002: Syntax error: }
(1192,134-135): run-time error JS1014: Invalid character: `
(1195,56-57): run-time error JS1195: Expected expression: )
(1195,58-59): run-time error JS1004: Expected ';': {
(1489,111-112): run-time error JS1014: Invalid character: `
(1489,130-131): run-time error JS1193: Expected ',' or ')': {
(1489,137-138): run-time error JS1195: Expected expression: ,
(1489,154-155): run-time error JS1195: Expected expression: ,
(1489,165-166): run-time error JS1195: Expected expression: ,
(1489,178-179): run-time error JS1014: Invalid character: `
(1489,179-180): run-time error JS1195: Expected expression: )
(1492,3-4): run-time error JS1002: Syntax error: }
(1495,51-52): run-time error JS1004: Expected ';': {
(2044,1-2): run-time error JS1002: Syntax error: }
(2045,13-14): run-time error JS1195: Expected expression: )
(2045,15-16): run-time error JS1004: Expected ';': {
(2780,2-3): run-time error JS1195: Expected expression: )
(2780,4-5): run-time error JS1197: Too many errors. The file might not be a JavaScript file: ;
(1583,3-15): run-time error JS1018: 'return' statement outside of function: return false
(1491,4-16): run-time error JS1018: 'return' statement outside of function: return false
(1209,3-15): run-time error JS1018: 'return' statement outside of function: return false
 */
(function($){var i=function(e){if(!e)var e=window.event;e.cancelBubble=true;if(e.stopPropagation)e.stopPropagation()};$.fn.checkbox=function(f){try{document.execCommand('BackgroundImageCache',false,true)}catch(e){}var g={cls:'jquery-checkbox',empty:'empty.png'};g=$.extend(g,f||{});var h=function(a){var b=a.checked;var c=a.disabled;var d=$(a);if(a.stateInterval)clearInterval(a.stateInterval);a.stateInterval=setInterval(function(){if(a.disabled!=c)d.trigger((c=!!a.disabled)?'disable':'enable');if(a.checked!=b)d.trigger((b=!!a.checked)?'check':'uncheck')},10);return d};return this.each(function(){var a=this;var b=h(a);if(a.wrapper)a.wrapper.remove();a.wrapper=$('<span class="'+g.cls+'"><span class="mark"><img src="'+g.empty+'" /></span></span>');a.wrapperInner=a.wrapper.children('span:eq(0)');a.wrapper.hover(function(e){a.wrapperInner.addClass(g.cls+'-hover');i(e)},function(e){a.wrapperInner.removeClass(g.cls+'-hover');i(e)});b.css({position:'absolute',zIndex:-1,visibility:'hidden'}).after(a.wrapper);var c=false;if(b.attr('id')){c=$('label[for='+b.attr('id')+']');if(!c.length)c=false}if(!c){c=b.closest?b.closest('label'):b.parents('label:eq(0)');if(!c.length)c=false}if(c){c.hover(function(e){a.wrapper.trigger('mouseover',[e])},function(e){a.wrapper.trigger('mouseout',[e])});c.click(function(e){b.trigger('click',[e]);i(e);return false})}a.wrapper.click(function(e){b.trigger('click',[e]);i(e);return false});b.click(function(e){i(e)});b.bind('disable',function(){a.wrapperInner.addClass(g.cls+'-disabled')}).bind('enable',function(){a.wrapperInner.removeClass(g.cls+'-disabled')});b.bind('check',function(){a.wrapper.addClass(g.cls+'-checked')}).bind('uncheck',function(){a.wrapper.removeClass(g.cls+'-checked')});$('img',a.wrapper).bind('dragstart',function(){return false}).bind('mousedown',function(){return false});if(window.getSelection)a.wrapper.css('MozUserSelect','none');if(a.checked)a.wrapper.addClass(g.cls+'-checked');if(a.disabled)a.wrapperInner.addClass(g.cls+'-disabled')})}})(jQuery);;
/*!
 * UAParser.js v0.7.21
 * Lightweight JavaScript-based User-Agent string parser
 * https://github.com/faisalman/ua-parser-js
 *
 * Copyright © 2012-2019 Faisal Salman <f@faisalman.com>
 * Licensed under MIT License
 */

(function (window, undefined) {

    //////////////
    // Constants
    /////////////


    var LIBVERSION  = '0.7.21',
        EMPTY       = '',
        UNKNOWN     = '?',
        FUNC_TYPE   = 'function',
        UNDEF_TYPE  = 'undefined',
        OBJ_TYPE    = 'object',
        STR_TYPE    = 'string',
        MAJOR       = 'major', // deprecated
        MODEL       = 'model',
        NAME        = 'name',
        TYPE        = 'type',
        VENDOR      = 'vendor',
        VERSION     = 'version',
        ARCHITECTURE= 'architecture',
        CONSOLE     = 'console',
        MOBILE      = 'mobile',
        TABLET      = 'tablet',
        SMARTTV     = 'smarttv',
        WEARABLE    = 'wearable',
        EMBEDDED    = 'embedded';


    ///////////
    // Helper
    //////////


    var util = {
        extend : function (regexes, extensions) {
            var mergedRegexes = {};
            for (var i in regexes) {
                if (extensions[i] && extensions[i].length % 2 === 0) {
                    mergedRegexes[i] = extensions[i].concat(regexes[i]);
                } else {
                    mergedRegexes[i] = regexes[i];
                }
            }
            return mergedRegexes;
        },
        has : function (str1, str2) {
          if (typeof str1 === "string") {
            return str2.toLowerCase().indexOf(str1.toLowerCase()) !== -1;
          } else {
            return false;
          }
        },
        lowerize : function (str) {
            return str.toLowerCase();
        },
        major : function (version) {
            return typeof(version) === STR_TYPE ? version.replace(/[^\d\.]/g,'').split(".")[0] : undefined;
        },
        trim : function (str) {
          return str.replace(/^[\s\uFEFF\xA0]+|[\s\uFEFF\xA0]+$/g, '');
        }
    };


    ///////////////
    // Map helper
    //////////////


    var mapper = {

        rgx : function (ua, arrays) {

            var i = 0, j, k, p, q, matches, match;

            // loop through all regexes maps
            while (i < arrays.length && !matches) {

                var regex = arrays[i],       // even sequence (0,2,4,..)
                    props = arrays[i + 1];   // odd sequence (1,3,5,..)
                j = k = 0;

                // try matching uastring with regexes
                while (j < regex.length && !matches) {

                    matches = regex[j++].exec(ua);

                    if (!!matches) {
                        for (p = 0; p < props.length; p++) {
                            match = matches[++k];
                            q = props[p];
                            // check if given property is actually array
                            if (typeof q === OBJ_TYPE && q.length > 0) {
                                if (q.length == 2) {
                                    if (typeof q[1] == FUNC_TYPE) {
                                        // assign modified match
                                        this[q[0]] = q[1].call(this, match);
                                    } else {
                                        // assign given value, ignore regex match
                                        this[q[0]] = q[1];
                                    }
                                } else if (q.length == 3) {
                                    // check whether function or regex
                                    if (typeof q[1] === FUNC_TYPE && !(q[1].exec && q[1].test)) {
                                        // call function (usually string mapper)
                                        this[q[0]] = match ? q[1].call(this, match, q[2]) : undefined;
                                    } else {
                                        // sanitize match using given regex
                                        this[q[0]] = match ? match.replace(q[1], q[2]) : undefined;
                                    }
                                } else if (q.length == 4) {
                                        this[q[0]] = match ? q[3].call(this, match.replace(q[1], q[2])) : undefined;
                                }
                            } else {
                                this[q] = match ? match : undefined;
                            }
                        }
                    }
                }
                i += 2;
            }
        },

        str : function (str, map) {

            for (var i in map) {
                // check if array
                if (typeof map[i] === OBJ_TYPE && map[i].length > 0) {
                    for (var j = 0; j < map[i].length; j++) {
                        if (util.has(map[i][j], str)) {
                            return (i === UNKNOWN) ? undefined : i;
                        }
                    }
                } else if (util.has(map[i], str)) {
                    return (i === UNKNOWN) ? undefined : i;
                }
            }
            return str;
        }
    };


    ///////////////
    // String map
    //////////////


    var maps = {

        browser : {
            oldsafari : {
                version : {
                    '1.0'   : '/8',
                    '1.2'   : '/1',
                    '1.3'   : '/3',
                    '2.0'   : '/412',
                    '2.0.2' : '/416',
                    '2.0.3' : '/417',
                    '2.0.4' : '/419',
                    '?'     : '/'
                }
            }
        },

        device : {
            amazon : {
                model : {
                    'Fire Phone' : ['SD', 'KF']
                }
            },
            sprint : {
                model : {
                    'Evo Shift 4G' : '7373KT'
                },
                vendor : {
                    'HTC'       : 'APA',
                    'Sprint'    : 'Sprint'
                }
            }
        },

        os : {
            windows : {
                version : {
                    'ME'        : '4.90',
                    'NT 3.11'   : 'NT3.51',
                    'NT 4.0'    : 'NT4.0',
                    '2000'      : 'NT 5.0',
                    'XP'        : ['NT 5.1', 'NT 5.2'],
                    'Vista'     : 'NT 6.0',
                    '7'         : 'NT 6.1',
                    '8'         : 'NT 6.2',
                    '8.1'       : 'NT 6.3',
                    '10'        : ['NT 6.4', 'NT 10.0'],
                    'RT'        : 'ARM'
                }
            }
        }
    };


    //////////////
    // Regex map
    /////////////


    var regexes = {

        browser : [[

            // Presto based
            /(opera\smini)\/([\w\.-]+)/i,                                       // Opera Mini
            /(opera\s[mobiletab]+).+version\/([\w\.-]+)/i,                      // Opera Mobi/Tablet
            /(opera).+version\/([\w\.]+)/i,                                     // Opera > 9.80
            /(opera)[\/\s]+([\w\.]+)/i                                          // Opera < 9.80
            ], [NAME, VERSION], [

            /(opios)[\/\s]+([\w\.]+)/i                                          // Opera mini on iphone >= 8.0
            ], [[NAME, 'Opera Mini'], VERSION], [

            /\s(opr)\/([\w\.]+)/i                                               // Opera Webkit
            ], [[NAME, 'Opera'], VERSION], [

            // Mixed
            /(kindle)\/([\w\.]+)/i,                                             // Kindle
            /(lunascape|maxthon|netfront|jasmine|blazer)[\/\s]?([\w\.]*)/i,
                                                                                // Lunascape/Maxthon/Netfront/Jasmine/Blazer
            // Trident based
            /(avant\s|iemobile|slim)(?:browser)?[\/\s]?([\w\.]*)/i,
                                                                                // Avant/IEMobile/SlimBrowser
            /(bidubrowser|baidubrowser)[\/\s]?([\w\.]+)/i,                      // Baidu Browser
            /(?:ms|\()(ie)\s([\w\.]+)/i,                                        // Internet Explorer

            // Webkit/KHTML based
            /(rekonq)\/([\w\.]*)/i,                                             // Rekonq
            /(chromium|flock|rockmelt|midori|epiphany|silk|skyfire|ovibrowser|bolt|iron|vivaldi|iridium|phantomjs|bowser|quark|qupzilla|falkon)\/([\w\.-]+)/i
                                                                                // Chromium/Flock/RockMelt/Midori/Epiphany/Silk/Skyfire/Bolt/Iron/Iridium/PhantomJS/Bowser/QupZilla/Falkon
            ], [NAME, VERSION], [

            /(konqueror)\/([\w\.]+)/i                                           // Konqueror
            ], [[NAME, 'Konqueror'], VERSION], [

            /(trident).+rv[:\s]([\w\.]+).+like\sgecko/i                         // IE11
            ], [[NAME, 'IE'], VERSION], [

            /(edge|edgios|edga|edg)\/((\d+)?[\w\.]+)/i                          // Microsoft Edge
            ], [[NAME, 'Edge'], VERSION], [

            /(yabrowser)\/([\w\.]+)/i                                           // Yandex
            ], [[NAME, 'Yandex'], VERSION], [

            /(Avast)\/([\w\.]+)/i                                               // Avast Secure Browser
            ], [[NAME, 'Avast Secure Browser'], VERSION], [

            /(AVG)\/([\w\.]+)/i                                                 // AVG Secure Browser
            ], [[NAME, 'AVG Secure Browser'], VERSION], [

            /(puffin)\/([\w\.]+)/i                                              // Puffin
            ], [[NAME, 'Puffin'], VERSION], [

            /(focus)\/([\w\.]+)/i                                               // Firefox Focus
            ], [[NAME, 'Firefox Focus'], VERSION], [

            /(opt)\/([\w\.]+)/i                                                 // Opera Touch
            ], [[NAME, 'Opera Touch'], VERSION], [

            /((?:[\s\/])uc?\s?browser|(?:juc.+)ucweb)[\/\s]?([\w\.]+)/i         // UCBrowser
            ], [[NAME, 'UCBrowser'], VERSION], [

            /(comodo_dragon)\/([\w\.]+)/i                                       // Comodo Dragon
            ], [[NAME, /_/g, ' '], VERSION], [

            /(windowswechat qbcore)\/([\w\.]+)/i                                // WeChat Desktop for Windows Built-in Browser
            ], [[NAME, 'WeChat(Win) Desktop'], VERSION], [

            /(micromessenger)\/([\w\.]+)/i                                      // WeChat
            ], [[NAME, 'WeChat'], VERSION], [

            /(brave)\/([\w\.]+)/i                                               // Brave browser
            ], [[NAME, 'Brave'], VERSION], [

            /(qqbrowserlite)\/([\w\.]+)/i                                       // QQBrowserLite
            ], [NAME, VERSION], [

            /(QQ)\/([\d\.]+)/i                                                  // QQ, aka ShouQ
            ], [NAME, VERSION], [

            /m?(qqbrowser)[\/\s]?([\w\.]+)/i                                    // QQBrowser
            ], [NAME, VERSION], [

            /(baiduboxapp)[\/\s]?([\w\.]+)/i                                    // Baidu App
            ], [NAME, VERSION], [

            /(2345Explorer)[\/\s]?([\w\.]+)/i                                   // 2345 Browser
            ], [NAME, VERSION], [

            /(MetaSr)[\/\s]?([\w\.]+)/i                                         // SouGouBrowser
            ], [NAME], [

            /(LBBROWSER)/i                                                      // LieBao Browser
            ], [NAME], [

            /xiaomi\/miuibrowser\/([\w\.]+)/i                                   // MIUI Browser
            ], [VERSION, [NAME, 'MIUI Browser']], [

            /;fbav\/([\w\.]+);/i                                                // Facebook App for iOS & Android
            ], [VERSION, [NAME, 'Facebook']], [

            /safari\s(line)\/([\w\.]+)/i,                                       // Line App for iOS
            /android.+(line)\/([\w\.]+)\/iab/i                                  // Line App for Android
            ], [NAME, VERSION], [

            /headlesschrome(?:\/([\w\.]+)|\s)/i                                 // Chrome Headless
            ], [VERSION, [NAME, 'Chrome Headless']], [

            /\swv\).+(chrome)\/([\w\.]+)/i                                      // Chrome WebView
            ], [[NAME, /(.+)/, '$1 WebView'], VERSION], [

            /((?:oculus|samsung)browser)\/([\w\.]+)/i
            ], [[NAME, /(.+(?:g|us))(.+)/, '$1 $2'], VERSION], [                // Oculus / Samsung Browser

            /android.+version\/([\w\.]+)\s+(?:mobile\s?safari|safari)*/i        // Android Browser
            ], [VERSION, [NAME, 'Android Browser']], [

            /(sailfishbrowser)\/([\w\.]+)/i                                     // Sailfish Browser
            ], [[NAME, 'Sailfish Browser'], VERSION], [

            /(chrome|omniweb|arora|[tizenoka]{5}\s?browser)\/v?([\w\.]+)/i
                                                                                // Chrome/OmniWeb/Arora/Tizen/Nokia
            ], [NAME, VERSION], [

            /(dolfin)\/([\w\.]+)/i                                              // Dolphin
            ], [[NAME, 'Dolphin'], VERSION], [

            /(qihu|qhbrowser|qihoobrowser|360browser)/i                         // 360
            ], [[NAME, '360 Browser']], [

            /((?:android.+)crmo|crios)\/([\w\.]+)/i                             // Chrome for Android/iOS
            ], [[NAME, 'Chrome'], VERSION], [

            /(coast)\/([\w\.]+)/i                                               // Opera Coast
            ], [[NAME, 'Opera Coast'], VERSION], [

            /fxios\/([\w\.-]+)/i                                                // Firefox for iOS
            ], [VERSION, [NAME, 'Firefox']], [

            /version\/([\w\.]+).+?mobile\/\w+\s(safari)/i                       // Mobile Safari
            ], [VERSION, [NAME, 'Mobile Safari']], [

            /version\/([\w\.]+).+?(mobile\s?safari|safari)/i                    // Safari & Safari Mobile
            ], [VERSION, NAME], [

            /webkit.+?(gsa)\/([\w\.]+).+?(mobile\s?safari|safari)(\/[\w\.]+)/i  // Google Search Appliance on iOS
            ], [[NAME, 'GSA'], VERSION], [

            /webkit.+?(mobile\s?safari|safari)(\/[\w\.]+)/i                     // Safari < 3.0
            ], [NAME, [VERSION, mapper.str, maps.browser.oldsafari.version]], [

            /(webkit|khtml)\/([\w\.]+)/i
            ], [NAME, VERSION], [

            // Gecko based
            /(navigator|netscape)\/([\w\.-]+)/i                                 // Netscape
            ], [[NAME, 'Netscape'], VERSION], [
            /(swiftfox)/i,                                                      // Swiftfox
            /(icedragon|iceweasel|camino|chimera|fennec|maemo\sbrowser|minimo|conkeror)[\/\s]?([\w\.\+]+)/i,
                                                                                // IceDragon/Iceweasel/Camino/Chimera/Fennec/Maemo/Minimo/Conkeror
            /(firefox|seamonkey|k-meleon|icecat|iceape|firebird|phoenix|palemoon|basilisk|waterfox)\/([\w\.-]+)$/i,

                                                                                // Firefox/SeaMonkey/K-Meleon/IceCat/IceApe/Firebird/Phoenix
            /(mozilla)\/([\w\.]+).+rv\:.+gecko\/\d+/i,                          // Mozilla

            // Other
            /(polaris|lynx|dillo|icab|doris|amaya|w3m|netsurf|sleipnir)[\/\s]?([\w\.]+)/i,
                                                                                // Polaris/Lynx/Dillo/iCab/Doris/Amaya/w3m/NetSurf/Sleipnir
            /(links)\s\(([\w\.]+)/i,                                            // Links
            /(gobrowser)\/?([\w\.]*)/i,                                         // GoBrowser
            /(ice\s?browser)\/v?([\w\._]+)/i,                                   // ICE Browser
            /(mosaic)[\/\s]([\w\.]+)/i                                          // Mosaic
            ], [NAME, VERSION]
        ],

        cpu : [[

            /(?:(amd|x(?:(?:86|64)[_-])?|wow|win)64)[;\)]/i                     // AMD64
            ], [[ARCHITECTURE, 'amd64']], [

            /(ia32(?=;))/i                                                      // IA32 (quicktime)
            ], [[ARCHITECTURE, util.lowerize]], [

            /((?:i[346]|x)86)[;\)]/i                                            // IA32
            ], [[ARCHITECTURE, 'ia32']], [

            // PocketPC mistakenly identified as PowerPC
            /windows\s(ce|mobile);\sppc;/i
            ], [[ARCHITECTURE, 'arm']], [

            /((?:ppc|powerpc)(?:64)?)(?:\smac|;|\))/i                           // PowerPC
            ], [[ARCHITECTURE, /ower/, '', util.lowerize]], [

            /(sun4\w)[;\)]/i                                                    // SPARC
            ], [[ARCHITECTURE, 'sparc']], [

            /((?:avr32|ia64(?=;))|68k(?=\))|arm(?:64|(?=v\d+[;l]))|(?=atmel\s)avr|(?:irix|mips|sparc)(?:64)?(?=;)|pa-risc)/i
                                                                                // IA64, 68K, ARM/64, AVR/32, IRIX/64, MIPS/64, SPARC/64, PA-RISC
            ], [[ARCHITECTURE, util.lowerize]]
        ],

        device : [[

            /\((ipad|playbook);[\w\s\),;-]+(rim|apple)/i                        // iPad/PlayBook
            ], [MODEL, VENDOR, [TYPE, TABLET]], [

            /applecoremedia\/[\w\.]+ \((ipad)/                                  // iPad
            ], [MODEL, [VENDOR, 'Apple'], [TYPE, TABLET]], [

            /(apple\s{0,1}tv)/i                                                 // Apple TV
            ], [[MODEL, 'Apple TV'], [VENDOR, 'Apple'], [TYPE, SMARTTV]], [

            /(archos)\s(gamepad2?)/i,                                           // Archos
            /(hp).+(touchpad)/i,                                                // HP TouchPad
            /(hp).+(tablet)/i,                                                  // HP Tablet
            /(kindle)\/([\w\.]+)/i,                                             // Kindle
            /\s(nook)[\w\s]+build\/(\w+)/i,                                     // Nook
            /(dell)\s(strea[kpr\s\d]*[\dko])/i                                  // Dell Streak
            ], [VENDOR, MODEL, [TYPE, TABLET]], [

            /(kf[A-z]+)\sbuild\/.+silk\//i                                      // Kindle Fire HD
            ], [MODEL, [VENDOR, 'Amazon'], [TYPE, TABLET]], [
            /(sd|kf)[0349hijorstuw]+\sbuild\/.+silk\//i                         // Fire Phone
            ], [[MODEL, mapper.str, maps.device.amazon.model], [VENDOR, 'Amazon'], [TYPE, MOBILE]], [
            /android.+aft([bms])\sbuild/i                                       // Fire TV
            ], [MODEL, [VENDOR, 'Amazon'], [TYPE, SMARTTV]], [

            /\((ip[honed|\s\w*]+);.+(apple)/i                                   // iPod/iPhone
            ], [MODEL, VENDOR, [TYPE, MOBILE]], [
            /\((ip[honed|\s\w*]+);/i                                            // iPod/iPhone
            ], [MODEL, [VENDOR, 'Apple'], [TYPE, MOBILE]], [

            /(blackberry)[\s-]?(\w+)/i,                                         // BlackBerry
            /(blackberry|benq|palm(?=\-)|sonyericsson|acer|asus|dell|meizu|motorola|polytron)[\s_-]?([\w-]*)/i,
                                                                                // BenQ/Palm/Sony-Ericsson/Acer/Asus/Dell/Meizu/Motorola/Polytron
            /(hp)\s([\w\s]+\w)/i,                                               // HP iPAQ
            /(asus)-?(\w+)/i                                                    // Asus
            ], [VENDOR, MODEL, [TYPE, MOBILE]], [
            /\(bb10;\s(\w+)/i                                                   // BlackBerry 10
            ], [MODEL, [VENDOR, 'BlackBerry'], [TYPE, MOBILE]], [
                                                                                // Asus Tablets
            /android.+(transfo[prime\s]{4,10}\s\w+|eeepc|slider\s\w+|nexus 7|padfone|p00c)/i
            ], [MODEL, [VENDOR, 'Asus'], [TYPE, TABLET]], [

            /(sony)\s(tablet\s[ps])\sbuild\//i,                                  // Sony
            /(sony)?(?:sgp.+)\sbuild\//i
            ], [[VENDOR, 'Sony'], [MODEL, 'Xperia Tablet'], [TYPE, TABLET]], [
            /android.+\s([c-g]\d{4}|so[-l]\w+)(?=\sbuild\/|\).+chrome\/(?![1-6]{0,1}\d\.))/i
            ], [MODEL, [VENDOR, 'Sony'], [TYPE, MOBILE]], [

            /\s(ouya)\s/i,                                                      // Ouya
            /(nintendo)\s([wids3u]+)/i                                          // Nintendo
            ], [VENDOR, MODEL, [TYPE, CONSOLE]], [

            /android.+;\s(shield)\sbuild/i                                      // Nvidia
            ], [MODEL, [VENDOR, 'Nvidia'], [TYPE, CONSOLE]], [

            /(playstation\s[34portablevi]+)/i                                   // Playstation
            ], [MODEL, [VENDOR, 'Sony'], [TYPE, CONSOLE]], [

            /(sprint\s(\w+))/i                                                  // Sprint Phones
            ], [[VENDOR, mapper.str, maps.device.sprint.vendor], [MODEL, mapper.str, maps.device.sprint.model], [TYPE, MOBILE]], [

            /(htc)[;_\s-]+([\w\s]+(?=\)|\sbuild)|\w+)/i,                        // HTC
            /(zte)-(\w*)/i,                                                     // ZTE
            /(alcatel|geeksphone|nexian|panasonic|(?=;\s)sony)[_\s-]?([\w-]*)/i
                                                                                // Alcatel/GeeksPhone/Nexian/Panasonic/Sony
            ], [VENDOR, [MODEL, /_/g, ' '], [TYPE, MOBILE]], [

            /(nexus\s9)/i                                                       // HTC Nexus 9
            ], [MODEL, [VENDOR, 'HTC'], [TYPE, TABLET]], [

            /d\/huawei([\w\s-]+)[;\)]/i,
            /(nexus\s6p|vog-l29|ane-lx1|eml-l29)/i                              // Huawei
            ], [MODEL, [VENDOR, 'Huawei'], [TYPE, MOBILE]], [

            /android.+(bah2?-a?[lw]\d{2})/i                                     // Huawei MediaPad
            ], [MODEL, [VENDOR, 'Huawei'], [TYPE, TABLET]], [

            /(microsoft);\s(lumia[\s\w]+)/i                                     // Microsoft Lumia
            ], [VENDOR, MODEL, [TYPE, MOBILE]], [

            /[\s\(;](xbox(?:\sone)?)[\s\);]/i                                   // Microsoft Xbox
            ], [MODEL, [VENDOR, 'Microsoft'], [TYPE, CONSOLE]], [
            /(kin\.[onetw]{3})/i                                                // Microsoft Kin
            ], [[MODEL, /\./g, ' '], [VENDOR, 'Microsoft'], [TYPE, MOBILE]], [

                                                                                // Motorola
            /\s(milestone|droid(?:[2-4x]|\s(?:bionic|x2|pro|razr))?:?(\s4g)?)[\w\s]+build\//i,
            /mot[\s-]?(\w*)/i,
            /(XT\d{3,4}) build\//i,
            /(nexus\s6)/i
            ], [MODEL, [VENDOR, 'Motorola'], [TYPE, MOBILE]], [
            /android.+\s(mz60\d|xoom[\s2]{0,2})\sbuild\//i
            ], [MODEL, [VENDOR, 'Motorola'], [TYPE, TABLET]], [

            /hbbtv\/\d+\.\d+\.\d+\s+\([\w\s]*;\s*(\w[^;]*);([^;]*)/i            // HbbTV devices
            ], [[VENDOR, util.trim], [MODEL, util.trim], [TYPE, SMARTTV]], [

            /hbbtv.+maple;(\d+)/i
            ], [[MODEL, /^/, 'SmartTV'], [VENDOR, 'Samsung'], [TYPE, SMARTTV]], [

            /\(dtv[\);].+(aquos)/i                                              // Sharp
            ], [MODEL, [VENDOR, 'Sharp'], [TYPE, SMARTTV]], [

            /android.+((sch-i[89]0\d|shw-m380s|gt-p\d{4}|gt-n\d+|sgh-t8[56]9|nexus 10))/i,
            /((SM-T\w+))/i
            ], [[VENDOR, 'Samsung'], MODEL, [TYPE, TABLET]], [                  // Samsung
            /smart-tv.+(samsung)/i
            ], [VENDOR, [TYPE, SMARTTV], MODEL], [
            /((s[cgp]h-\w+|gt-\w+|galaxy\snexus|sm-\w[\w\d]+))/i,
            /(sam[sung]*)[\s-]*(\w+-?[\w-]*)/i,
            /sec-((sgh\w+))/i
            ], [[VENDOR, 'Samsung'], MODEL, [TYPE, MOBILE]], [

            /sie-(\w*)/i                                                        // Siemens
            ], [MODEL, [VENDOR, 'Siemens'], [TYPE, MOBILE]], [

            /(maemo|nokia).*(n900|lumia\s\d+)/i,                                // Nokia
            /(nokia)[\s_-]?([\w-]*)/i
            ], [[VENDOR, 'Nokia'], MODEL, [TYPE, MOBILE]], [

            /android[x\d\.\s;]+\s([ab][1-7]\-?[0178a]\d\d?)/i                   // Acer
            ], [MODEL, [VENDOR, 'Acer'], [TYPE, TABLET]], [

            /android.+([vl]k\-?\d{3})\s+build/i                                 // LG Tablet
            ], [MODEL, [VENDOR, 'LG'], [TYPE, TABLET]], [
            /android\s3\.[\s\w;-]{10}(lg?)-([06cv9]{3,4})/i                     // LG Tablet
            ], [[VENDOR, 'LG'], MODEL, [TYPE, TABLET]], [
            /(lg) netcast\.tv/i                                                 // LG SmartTV
            ], [VENDOR, MODEL, [TYPE, SMARTTV]], [
            /(nexus\s[45])/i,                                                   // LG
            /lg[e;\s\/-]+(\w*)/i,
            /android.+lg(\-?[\d\w]+)\s+build/i
            ], [MODEL, [VENDOR, 'LG'], [TYPE, MOBILE]], [

            /(lenovo)\s?(s(?:5000|6000)(?:[\w-]+)|tab(?:[\s\w]+))/i             // Lenovo tablets
            ], [VENDOR, MODEL, [TYPE, TABLET]], [
            /android.+(ideatab[a-z0-9\-\s]+)/i                                  // Lenovo
            ], [MODEL, [VENDOR, 'Lenovo'], [TYPE, TABLET]], [
            /(lenovo)[_\s-]?([\w-]+)/i
            ], [VENDOR, MODEL, [TYPE, MOBILE]], [

            /linux;.+((jolla));/i                                               // Jolla
            ], [VENDOR, MODEL, [TYPE, MOBILE]], [

            /((pebble))app\/[\d\.]+\s/i                                         // Pebble
            ], [VENDOR, MODEL, [TYPE, WEARABLE]], [

            /android.+;\s(oppo)\s?([\w\s]+)\sbuild/i                            // OPPO
            ], [VENDOR, MODEL, [TYPE, MOBILE]], [

            /crkey/i                                                            // Google Chromecast
            ], [[MODEL, 'Chromecast'], [VENDOR, 'Google'], [TYPE, SMARTTV]], [

            /android.+;\s(glass)\s\d/i                                          // Google Glass
            ], [MODEL, [VENDOR, 'Google'], [TYPE, WEARABLE]], [

            /android.+;\s(pixel c)[\s)]/i                                       // Google Pixel C
            ], [MODEL, [VENDOR, 'Google'], [TYPE, TABLET]], [

            /android.+;\s(pixel( [23])?( xl)?)[\s)]/i                              // Google Pixel
            ], [MODEL, [VENDOR, 'Google'], [TYPE, MOBILE]], [

            /android.+;\s(\w+)\s+build\/hm\1/i,                                 // Xiaomi Hongmi 'numeric' models
            /android.+(hm[\s\-_]*note?[\s_]*(?:\d\w)?)\s+build/i,               // Xiaomi Hongmi
            /android.+(mi[\s\-_]*(?:a\d|one|one[\s_]plus|note lte)?[\s_]*(?:\d?\w?)[\s_]*(?:plus)?)\s+build/i,
                                                                                // Xiaomi Mi
            /android.+(redmi[\s\-_]*(?:note)?(?:[\s_]*[\w\s]+))\s+build/i       // Redmi Phones
            ], [[MODEL, /_/g, ' '], [VENDOR, 'Xiaomi'], [TYPE, MOBILE]], [
            /android.+(mi[\s\-_]*(?:pad)(?:[\s_]*[\w\s]+))\s+build/i            // Mi Pad tablets
            ],[[MODEL, /_/g, ' '], [VENDOR, 'Xiaomi'], [TYPE, TABLET]], [
            /android.+;\s(m[1-5]\snote)\sbuild/i                                // Meizu
            ], [MODEL, [VENDOR, 'Meizu'], [TYPE, MOBILE]], [
            /(mz)-([\w-]{2,})/i
            ], [[VENDOR, 'Meizu'], MODEL, [TYPE, MOBILE]], [

            /android.+a000(1)\s+build/i,                                        // OnePlus
            /android.+oneplus\s(a\d{4})[\s)]/i
            ], [MODEL, [VENDOR, 'OnePlus'], [TYPE, MOBILE]], [

            /android.+[;\/]\s*(RCT[\d\w]+)\s+build/i                            // RCA Tablets
            ], [MODEL, [VENDOR, 'RCA'], [TYPE, TABLET]], [

            /android.+[;\/\s]+(Venue[\d\s]{2,7})\s+build/i                      // Dell Venue Tablets
            ], [MODEL, [VENDOR, 'Dell'], [TYPE, TABLET]], [

            /android.+[;\/]\s*(Q[T|M][\d\w]+)\s+build/i                         // Verizon Tablet
            ], [MODEL, [VENDOR, 'Verizon'], [TYPE, TABLET]], [

            /android.+[;\/]\s+(Barnes[&\s]+Noble\s+|BN[RT])(V?.*)\s+build/i     // Barnes & Noble Tablet
            ], [[VENDOR, 'Barnes & Noble'], MODEL, [TYPE, TABLET]], [

            /android.+[;\/]\s+(TM\d{3}.*\b)\s+build/i                           // Barnes & Noble Tablet
            ], [MODEL, [VENDOR, 'NuVision'], [TYPE, TABLET]], [

            /android.+;\s(k88)\sbuild/i                                         // ZTE K Series Tablet
            ], [MODEL, [VENDOR, 'ZTE'], [TYPE, TABLET]], [

            /android.+[;\/]\s*(gen\d{3})\s+build.*49h/i                         // Swiss GEN Mobile
            ], [MODEL, [VENDOR, 'Swiss'], [TYPE, MOBILE]], [

            /android.+[;\/]\s*(zur\d{3})\s+build/i                              // Swiss ZUR Tablet
            ], [MODEL, [VENDOR, 'Swiss'], [TYPE, TABLET]], [

            /android.+[;\/]\s*((Zeki)?TB.*\b)\s+build/i                         // Zeki Tablets
            ], [MODEL, [VENDOR, 'Zeki'], [TYPE, TABLET]], [

            /(android).+[;\/]\s+([YR]\d{2})\s+build/i,
            /android.+[;\/]\s+(Dragon[\-\s]+Touch\s+|DT)(\w{5})\sbuild/i        // Dragon Touch Tablet
            ], [[VENDOR, 'Dragon Touch'], MODEL, [TYPE, TABLET]], [

            /android.+[;\/]\s*(NS-?\w{0,9})\sbuild/i                            // Insignia Tablets
            ], [MODEL, [VENDOR, 'Insignia'], [TYPE, TABLET]], [

            /android.+[;\/]\s*((NX|Next)-?\w{0,9})\s+build/i                    // NextBook Tablets
            ], [MODEL, [VENDOR, 'NextBook'], [TYPE, TABLET]], [

            /android.+[;\/]\s*(Xtreme\_)?(V(1[045]|2[015]|30|40|60|7[05]|90))\s+build/i
            ], [[VENDOR, 'Voice'], MODEL, [TYPE, MOBILE]], [                    // Voice Xtreme Phones

            /android.+[;\/]\s*(LVTEL\-)?(V1[12])\s+build/i                     // LvTel Phones
            ], [[VENDOR, 'LvTel'], MODEL, [TYPE, MOBILE]], [

            /android.+;\s(PH-1)\s/i
            ], [MODEL, [VENDOR, 'Essential'], [TYPE, MOBILE]], [                // Essential PH-1

            /android.+[;\/]\s*(V(100MD|700NA|7011|917G).*\b)\s+build/i          // Envizen Tablets
            ], [MODEL, [VENDOR, 'Envizen'], [TYPE, TABLET]], [

            /android.+[;\/]\s*(Le[\s\-]+Pan)[\s\-]+(\w{1,9})\s+build/i          // Le Pan Tablets
            ], [VENDOR, MODEL, [TYPE, TABLET]], [

            /android.+[;\/]\s*(Trio[\s\-]*.*)\s+build/i                         // MachSpeed Tablets
            ], [MODEL, [VENDOR, 'MachSpeed'], [TYPE, TABLET]], [

            /android.+[;\/]\s*(Trinity)[\-\s]*(T\d{3})\s+build/i                // Trinity Tablets
            ], [VENDOR, MODEL, [TYPE, TABLET]], [

            /android.+[;\/]\s*TU_(1491)\s+build/i                               // Rotor Tablets
            ], [MODEL, [VENDOR, 'Rotor'], [TYPE, TABLET]], [

            /android.+(KS(.+))\s+build/i                                        // Amazon Kindle Tablets
            ], [MODEL, [VENDOR, 'Amazon'], [TYPE, TABLET]], [

            /android.+(Gigaset)[\s\-]+(Q\w{1,9})\s+build/i                      // Gigaset Tablets
            ], [VENDOR, MODEL, [TYPE, TABLET]], [

            /\s(tablet|tab)[;\/]/i,                                             // Unidentifiable Tablet
            /\s(mobile)(?:[;\/]|\ssafari)/i                                     // Unidentifiable Mobile
            ], [[TYPE, util.lowerize], VENDOR, MODEL], [

            /[\s\/\(](smart-?tv)[;\)]/i                                         // SmartTV
            ], [[TYPE, SMARTTV]], [

            /(android[\w\.\s\-]{0,9});.+build/i                                 // Generic Android Device
            ], [MODEL, [VENDOR, 'Generic']]
        ],

        engine : [[

            /windows.+\sedge\/([\w\.]+)/i                                       // EdgeHTML
            ], [VERSION, [NAME, 'EdgeHTML']], [

            /webkit\/537\.36.+chrome\/(?!27)([\w\.]+)/i                         // Blink
            ], [VERSION, [NAME, 'Blink']], [

            /(presto)\/([\w\.]+)/i,                                             // Presto
            /(webkit|trident|netfront|netsurf|amaya|lynx|w3m|goanna)\/([\w\.]+)/i,
                                                                                // WebKit/Trident/NetFront/NetSurf/Amaya/Lynx/w3m/Goanna
            /(khtml|tasman|links)[\/\s]\(?([\w\.]+)/i,                          // KHTML/Tasman/Links
            /(icab)[\/\s]([23]\.[\d\.]+)/i                                      // iCab
            ], [NAME, VERSION], [

            /rv\:([\w\.]{1,9}).+(gecko)/i                                       // Gecko
            ], [VERSION, NAME]
        ],

        os : [[

            // Windows based
            /microsoft\s(windows)\s(vista|xp)/i                                 // Windows (iTunes)
            ], [NAME, VERSION], [
            /(windows)\snt\s6\.2;\s(arm)/i,                                     // Windows RT
            /(windows\sphone(?:\sos)*)[\s\/]?([\d\.\s\w]*)/i,                   // Windows Phone
            /(windows\smobile|windows)[\s\/]?([ntce\d\.\s]+\w)/i
            ], [NAME, [VERSION, mapper.str, maps.os.windows.version]], [
            /(win(?=3|9|n)|win\s9x\s)([nt\d\.]+)/i
            ], [[NAME, 'Windows'], [VERSION, mapper.str, maps.os.windows.version]], [

            // Mobile/Embedded OS
            /\((bb)(10);/i                                                      // BlackBerry 10
            ], [[NAME, 'BlackBerry'], VERSION], [
            /(blackberry)\w*\/?([\w\.]*)/i,                                     // Blackberry
            /(tizen|kaios)[\/\s]([\w\.]+)/i,                                    // Tizen/KaiOS
            /(android|webos|palm\sos|qnx|bada|rim\stablet\sos|meego|sailfish|contiki)[\/\s-]?([\w\.]*)/i
                                                                                // Android/WebOS/Palm/QNX/Bada/RIM/MeeGo/Contiki/Sailfish OS
            ], [NAME, VERSION], [
            /(symbian\s?os|symbos|s60(?=;))[\/\s-]?([\w\.]*)/i                  // Symbian
            ], [[NAME, 'Symbian'], VERSION], [
            /\((series40);/i                                                    // Series 40
            ], [NAME], [
            /mozilla.+\(mobile;.+gecko.+firefox/i                               // Firefox OS
            ], [[NAME, 'Firefox OS'], VERSION], [

            // Console
            /(nintendo|playstation)\s([wids34portablevu]+)/i,                   // Nintendo/Playstation

            // GNU/Linux based
            /(mint)[\/\s\(]?(\w*)/i,                                            // Mint
            /(mageia|vectorlinux)[;\s]/i,                                       // Mageia/VectorLinux
            /(joli|[kxln]?ubuntu|debian|suse|opensuse|gentoo|(?=\s)arch|slackware|fedora|mandriva|centos|pclinuxos|redhat|zenwalk|linpus)[\/\s-]?(?!chrom)([\w\.-]*)/i,
                                                                                // Joli/Ubuntu/Debian/SUSE/Gentoo/Arch/Slackware
                                                                                // Fedora/Mandriva/CentOS/PCLinuxOS/RedHat/Zenwalk/Linpus
            /(hurd|linux)\s?([\w\.]*)/i,                                        // Hurd/Linux
            /(gnu)\s?([\w\.]*)/i                                                // GNU
            ], [NAME, VERSION], [

            /(cros)\s[\w]+\s([\w\.]+\w)/i                                       // Chromium OS
            ], [[NAME, 'Chromium OS'], VERSION],[

            // Solaris
            /(sunos)\s?([\w\.\d]*)/i                                            // Solaris
            ], [[NAME, 'Solaris'], VERSION], [

            // BSD based
            /\s([frentopc-]{0,4}bsd|dragonfly)\s?([\w\.]*)/i                    // FreeBSD/NetBSD/OpenBSD/PC-BSD/DragonFly
            ], [NAME, VERSION],[

            /(haiku)\s(\w+)/i                                                   // Haiku
            ], [NAME, VERSION],[

            /cfnetwork\/.+darwin/i,
            /ip[honead]{2,4}(?:.*os\s([\w]+)\slike\smac|;\sopera)/i             // iOS
            ], [[VERSION, /_/g, '.'], [NAME, 'iOS']], [

            /(mac\sos\sx)\s?([\w\s\.]*)/i,
            /(macintosh|mac(?=_powerpc)\s)/i                                    // Mac OS
            ], [[NAME, 'Mac OS'], [VERSION, /_/g, '.']], [

            // Other
            /((?:open)?solaris)[\/\s-]?([\w\.]*)/i,                             // Solaris
            /(aix)\s((\d)(?=\.|\)|\s)[\w\.])*/i,                                // AIX
            /(plan\s9|minix|beos|os\/2|amigaos|morphos|risc\sos|openvms|fuchsia)/i,
                                                                                // Plan9/Minix/BeOS/OS2/AmigaOS/MorphOS/RISCOS/OpenVMS/Fuchsia
            /(unix)\s?([\w\.]*)/i                                               // UNIX
            ], [NAME, VERSION]
        ]
    };


    /////////////////
    // Constructor
    ////////////////
    var UAParser = function (uastring, extensions) {

        if (typeof uastring === 'object') {
            extensions = uastring;
            uastring = undefined;
        }

        if (!(this instanceof UAParser)) {
            return new UAParser(uastring, extensions).getResult();
        }

        var ua = uastring || ((window && window.navigator && window.navigator.userAgent) ? window.navigator.userAgent : EMPTY);
        var rgxmap = extensions ? util.extend(regexes, extensions) : regexes;

        this.getBrowser = function () {
            var browser = { name: undefined, version: undefined };
            mapper.rgx.call(browser, ua, rgxmap.browser);
            browser.major = util.major(browser.version); // deprecated
            return browser;
        };
        this.getCPU = function () {
            var cpu = { architecture: undefined };
            mapper.rgx.call(cpu, ua, rgxmap.cpu);
            return cpu;
        };
        this.getDevice = function () {
            var device = { vendor: undefined, model: undefined, type: undefined };
            mapper.rgx.call(device, ua, rgxmap.device);
            return device;
        };
        this.getEngine = function () {
            var engine = { name: undefined, version: undefined };
            mapper.rgx.call(engine, ua, rgxmap.engine);
            return engine;
        };
        this.getOS = function () {
            var os = { name: undefined, version: undefined };
            mapper.rgx.call(os, ua, rgxmap.os);
            return os;
        };
        this.getResult = function () {
            return {
                ua      : this.getUA(),
                browser : this.getBrowser(),
                engine  : this.getEngine(),
                os      : this.getOS(),
                device  : this.getDevice(),
                cpu     : this.getCPU()
            };
        };
        this.getUA = function () {
            return ua;
        };
        this.setUA = function (uastring) {
            ua = uastring;
            return this;
        };
        return this;
    };

    UAParser.VERSION = LIBVERSION;
    UAParser.BROWSER = {
        NAME    : NAME,
        MAJOR   : MAJOR, // deprecated
        VERSION : VERSION
    };
    UAParser.CPU = {
        ARCHITECTURE : ARCHITECTURE
    };
    UAParser.DEVICE = {
        MODEL   : MODEL,
        VENDOR  : VENDOR,
        TYPE    : TYPE,
        CONSOLE : CONSOLE,
        MOBILE  : MOBILE,
        SMARTTV : SMARTTV,
        TABLET  : TABLET,
        WEARABLE: WEARABLE,
        EMBEDDED: EMBEDDED
    };
    UAParser.ENGINE = {
        NAME    : NAME,
        VERSION : VERSION
    };
    UAParser.OS = {
        NAME    : NAME,
        VERSION : VERSION
    };

    ///////////
    // Export
    //////////


    // check js environment
    if (typeof(exports) !== UNDEF_TYPE) {
        // nodejs env
        if (typeof module !== UNDEF_TYPE && module.exports) {
            exports = module.exports = UAParser;
        }
        exports.UAParser = UAParser;
    } else {
        // requirejs env (optional)
        if (typeof(define) === 'function' && define.amd) {
            define(function () {
                return UAParser;
            });
        } else if (window) {
            // browser env
            window.UAParser = UAParser;
        }
    }

    // jQuery/Zepto specific (optional)
    // Note:
    //   In AMD env the global scope should be kept clean, but jQuery is an exception.
    //   jQuery always exports to global scope, unless jQuery.noConflict(true) is used,
    //   and we should catch that.
    var $ = window && (window.jQuery || window.Zepto);
    if ($ && !$.ua) {
        var parser = new UAParser();
        $.ua = parser.getResult();
        $.ua.get = function () {
            return parser.getUA();
        };
        $.ua.set = function (uastring) {
            parser.setUA(uastring);
            var result = parser.getResult();
            for (var prop in result) {
                $.ua[prop] = result[prop];
            }
        };
    }

})(typeof window === 'object' ? window : this);
;
$(function () {
	var ModalLogon = function () {
			var isOldIE = $.browser.msie && parseInt($.browser.version, 10) < 9;

			if (!isOldIE) {
				this.redirectUrl = '';
				this.esiaRedirectAddress = '';
				this.template = $('#modal_logon').html();
				this.partials = {};
				this.isNoToggle = false;
				this.isEsiaRequired = false;
				this.defaultMode = 'esia';
				this.mode = this.defaultMode;
				this.prevMode = null;
				this.inputNamesMap = null;
				this._req = {};

				this.validateRules = {
					logOn: {
						UserName: {
							rules: ['required', 'encoded_uri_email'],
							message: 'Нужно указать корректный адрес электронной почты'
						},
						Password: {
							rules: ['required'],
							message: 'Пароль не может быть пустым'
						}
					},
					restorePassword: {
						Email: {
							rules: ['required', 'email'],
							message: 'Нужно указать корректный адрес электронной почты'
						}
					},
					linkEsiaAccount: {
						Email: {
							rules: ['required', 'email'],
							message: 'Нужно указать корректный адрес электронной почты'
						}
					},
					registerUser: {
						FirstName: {
							rules: ['required'],
							message: 'Укажите имя'
						},
						LastName: {
							rules: ['required'],
							message: 'Укажите фамилию'
						},
						UserName: {
							rules: ['required', 'email'],
							message: 'Укажите корректный адрес электронной почты'
						},
						Phone: {
							rules: ['required'],
							message: 'Укажите номер мобильного телефона'
						},
						Password: {
							rules: ['required'],
							message: 'Укажите пароль'
						},
						ConfirmPassword: {
							rules: ['confirm_password']
						}
					}
				};

				this.validators = {
					required: function(value) {
						return {
							status: !!$.trim(value),
							message: 'Поле не должно быть пустым'
						}
					},
					email: function(value) {
						return {
							status: !value || /[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?/.test(value.toLowerCase()),
							message: 'Некорректный email'
						}
					},
					encoded_uri_email: function (value) {
						return this.email(decodeURIComponent(value));
					},
					confirm_password: function (value, data) {
						var status = true;
							message = null;

						if (data.Password) {
							status = !!data.ConfirmPassword;

							if (status) {
								status = data.Password === data.ConfirmPassword;

								if (!status) {
									message = 'Пароли не совпадают';
								}
							} else {
								message = 'Повторно введите пароль';
							}
						}

						return {
							status: status,
							message: message
						};
					},
				};

				this.initialize();
			}
		};

	ModalLogon.prototype.delegateEvents = function () {
		this.$el
			.delegate('.js-modal_logon-prevent_event', 'click keyup keydown', this.preventEvent)
			.delegate('.js-popup-close', 'click', this.hide.bind(this))
			.delegate('.js-modal_logon-mode-toggler', 'click', this.toggleMode.bind(this))
			.delegate('.js-modal_logon-form-input_placeholder', 'click', this.clickInputPlaceholder)
			.delegate('.js-modal_logon-form-input', 'change', this.togglePlaceholder.bind(this))
			.delegate('.js-modal_logon-form-input', 'focus', this.focusInput)
			.delegate('.js-modal_logon-form-input', 'blur', this.blurInput.bind(this))
			.delegate('.js-modal_logon-form-input', 'keyup', this.keyupInput.bind(this))
			.delegate('.js-modal_logon-logon', 'click', this.logOn.bind(this))
			.delegate('.js-modal_logon-registeruser', 'click', this.registerUser.bind(this))
			.delegate('.js-modal_logon-restorepassword', 'click', this.restorePassword.bind(this))
			.delegate('.js-modal_logon-linkesiaaccount', 'click', this.linkEsiaAccount.bind(this))
			.delegate('.js-modal_logon-openauthpage', 'click', this.openAuthPageByButton.bind(this))
			.delegate('.js-modal_logon-logon_form', 'submit', this.preventEvent)
			.delegate('.js-modal_logon-restorepassword_form, .js-modal_logon-linkesiaaccount_form', 'submit', this.preventEvent)
			.delegate('input[name="RememberMe"]', 'change', this.toggleRememberMeCheckbox.bind(this))
			.delegate('input[name="IAgree"]', 'change', this.toggleIAgreeCheckbox.bind(this))
			.delegate('.js-modal_logon-esia', 'click', function () {
				this.setIAgreeFlag();
				this.saveSearchParams();
			}.bind(this));
	};

	ModalLogon.prototype.initialize = function () {
		var isAuth = !$('.js-arbitr-header-auth-name').length && (Common.getUrlParam('auth') === 'true'),
			returnUrlString = (Common.getUrlParam('returnUrl') || Common.getUrlParam('ReturnUrl')) + location.hash;

		this.isIframe = window.self !== window.top;

		if (isAuth) {
			setTimeout(function () {
				this.show({
					mode: this.isIframe ? 'openauthpage' : this.defaultMode,
					esiaRedirectAddress: returnUrlString,
					redirectUrl: returnUrlString
				});
			}.bind(this), 0);
		} else if (returnUrlString) {
			location.href = returnUrlString;
		}

		$('.js-sj_auth').bind('click', function () {
			return this.show();
		}.bind(this));

		$('.js-sj_logout').bind('click', function (e) {
			return this.openLogOffPage(e.currentTarget.href);
		}.bind(this));

		this.$el = $('<div class="b-modal">');

		this.$modal = $('<div class="b-modal_wrapper">');

		this.$modal.appendTo('body');
	};

	ModalLogon.prototype.render = function (params) {
		this.$el.html(this.template);

		this.partials.modeBlocks = {};
		this.partials.modeBlocks.$logonBlocks = this.$el.find('.js-mode--logon');
		this.partials.modeBlocks.$registeruserBlocks = this.$el.find('.js-mode--registeruser');
		this.partials.modeBlocks.$esiaBlocks = this.$el.find('.js-mode--esia');
		this.partials.modeBlocks.$restorepasswordBlocks = this.$el.find('.js-mode--restorepassword');
		this.partials.modeBlocks.$linkesiaaccountBlocks = this.$el.find('.js-mode--linkesiaaccount');
		this.partials.modeBlocks.$openauthpageBlocks = this.$el.find('.js-mode--openauthpage');
		this.partials.$logonForm = this.$el.find('.js-modal_logon-logon_form');
		this.partials.$registeruserForm = this.$el.find('.js-modal_logon-registeruser_form');
		this.partials.$restorepasswordForm = this.$el.find('.js-modal_logon-restorepassword_form');
		this.partials.$linkesiaaccountForm = this.$el.find('.js-modal_logon-linkesiaaccount_form');
		this.partials.$esiaLink = this.$el.find('.js-modal_logon-esia');
		this.partials.$backModeToggler = this.$el.find('.js-modal_logon-mode-toggler--back');

		this.initInputNamesMap();

		if ($.cookie('is_agree_privacy_policy')) {
			this.$el.find('input[name="IAgree"]').attr('checked', true);
			$.cookie('is_agree_privacy_policy', null);
		}

		this.toggleIAgreeCheckbox();

		var phoneMask = '+7 999 999-99-99';

		$('.js-modal_logon-form-input--phone', this.$el)
			.attr('data-mask', phoneMask)
			.mask(phoneMask);

		this.toggleMode(params.mode || this.mode);

		this.$el.appendTo(this.$modal);

		this.delegateEvents();
	};

	ModalLogon.prototype.remove = function () {
		this.$el.remove();
	};

	ModalLogon.prototype.show = function (params) {
		params = params || {};

		if (this.isIframe && ['openauthpage', 'restorepassword'].indexOf(params.mode) === -1) {
			this.saveSearchParams();

			this.openAuthPage({
				params: JSON.stringify(params),
				isEsia: (params.isNoToggle || params.isEsiaRequired) && (!params.mode || params.mode === 'esia')
			});

			return false;
		}

		this.isBlocker = !!params.isBlocker;
		this.isPopup = !!params.isPopup;
		this.isNoToggle = !!params.isNoToggle;
		this.isEsiaRequired = !!params.isEsiaRequired;
		this.esiaRedirectAddress = encodeURIComponent(params.esiaRedirectAddress ?
								   params.esiaRedirectAddress :
								   location.pathname + location.search + location.hash);

		if (this.esiaRedirectAddress) {
			this.esiaRedirectAddress = 'redirectTo=' + this.esiaRedirectAddress;
		}

		this.redirectUrl = params.redirectUrl || '';

		this.$modal.hide();

		this.render(params);

		if (this.isEsiaRequired) {
			this.$el.find('.js-modal_logon-mode').text('Функция доступна только при входе через портал Госуслуг');
		} else if (this.isNoToggle) {
			this.$el.find('.js-modal_logon-mode').remove();
		}

		if (this.esiaRedirectAddress) {
			this.partials.$esiaLink.attr('href', this.partials.$esiaLink.attr('href') + '?' + this.esiaRedirectAddress);
		}

		this.$modal.show();

		if (this.isBlocker) {
			this.$el.find('.js-popup-close').remove();
		} else {
			this.toggleEscListener(true);
		}

		return false;
	};

	ModalLogon.prototype.openAuthPage = function (params) {
		var width = Math.min(800, screen.availWidth),
			height = Math.min(800, screen.availHeight),
			left = (screen.width - width) / 2,
			top = (screen.height - height) / 2,
			paramsString = '';

		if (Object.keys(params || {}).length) {
			paramsString = '?';

			for (var key in params) {
				paramsString += key + '=' + encodeURIComponent(params[key]) + '&';
			}

			paramsString = paramsString.substring(0, paramsString.length - 1);
		}

		window.open(location.origin + '/Kad/Auth' + paramsString, null, `popup=true,width=${width},height=${height},top=${top},left=${left}`);
	};

	ModalLogon.prototype.openAuthPageByButton = function () {
		var params = {
				isBlocker: this.isBlocker,
				isNoToggle: this.isNoToggle,
				isEsiaRequired: this.isEsiaRequired,
				esiaRedirectAddress: this.esiaRedirectAddress,
				redirectUrl: this.redirectUrl
			};

		this.openAuthPage({
			params: JSON.stringify(params),
			isEsia: params.isNoToggle || params.isEsiaRequired
		});

		return false;
	};

	ModalLogon.prototype.hide = function () {
		this.remove();

		this.mode = this.defaultMode;
		this.prevMode = null;

		this.$modal.hide();
		this.toggleEscListener();

		return false;
	};

	ModalLogon.prototype.toggleEscListener = function (on) {
		$($.browser.msie ? 'body' : window)[on ? 'bind' : 'unbind']('keyup.modal_logon_esc_close', on && function(event) {
			if (event && event.keyCode == 27) {
				var logOnRequest = this._req && this._req.logOn,
					restorePasswordRequest = this._req && this._req.restorePassword,
					linkEsiaAccountRequest = this._req && this._req.linkEsiaAccount,
					registerUserRequest = this._req && this._req.registerUser;

				if (!logOnRequest || !logOnRequest.readyState || logOnRequest.readyState === 4) {
					if (!restorePasswordRequest || !restorePasswordRequest.readyState || restorePasswordRequest.readyState === 4) {
						if (!linkEsiaAccountRequest || !linkEsiaAccountRequest.readyState || linkEsiaAccountRequest.readyState === 4) {
							if (!registerUserRequest || !registerUserRequest.readyState || registerUserRequest.readyState === 4) {
								this.hide();
							}
						}
					}
				}
			}
		}.bind(this));
	};

	ModalLogon.prototype.toggleMode = function (e) {
		var mode = typeof e === 'string' ? e : e.currentTarget.getAttribute('href'),
			$selectingModeBlocks = this.partials.modeBlocks['$' + mode + 'Blocks'];

		for (var key in this.partials.modeBlocks) {
			if (this.partials.modeBlocks.hasOwnProperty(key)) {
				this.partials.modeBlocks[key].addClass('g-hidden');
			}
		}

		this.prevMode = this.mode;
		this.mode = mode;

		$selectingModeBlocks.removeClass('g-hidden');

		var $firstTextInput = $selectingModeBlocks.find('input[type="text"]:first');

		if ($firstTextInput.length) {
			$firstTextInput.focus();
		}

		this.$el[0].className = 'b-modal b-modal--' + this.mode;

		this.partials.$backModeToggler.attr('href', this.prevMode);

		return false;
	};

	ModalLogon.prototype.clickInputPlaceholder = function (e) {
		var $placeholder = $(e.currentTarget),
			$wrapper = $placeholder.parent(),
			$input = $wrapper.find('.js-modal_logon-form-input'),
			$label = $wrapper.find('.js-modal_logon-form-label');

		$placeholder.addClass('g-hidden');
		$label.removeClass('g-hidden');
		$input.focus();
	};

	ModalLogon.prototype.focusInput = function (e) {
		var $input = $(e.currentTarget),
			$wrapper = $input.parent(),
			$placeholder = $wrapper.find('.js-modal_logon-form-input_placeholder'),
			$error = $wrapper.find('.js-modal_logon-form-input_error'),
			$label;

		if (!$placeholder.hasClass('g-hidden')) {
			$label = $wrapper.find('.js-modal_logon-form-label');

			$placeholder.addClass('g-hidden');
			$label.removeClass('g-hidden');
		}

		if (!$error.hasClass('g-hidden')) {
			$error.addClass('g-hidden');
		}
	};

	ModalLogon.prototype.blurInput = function (e) {
		if (e.currentTarget.getAttribute('data-mask')) {
			setTimeout(function () {
				this._blurInput(e);
			}.bind(this));
		} else {
			this._blurInput(e);
		}
	};

	ModalLogon.prototype._blurInput = function (e) {
		var $input = $(e.currentTarget),
			$wrapper = $input.parent(),
			$error = $wrapper.find('.js-modal_logon-form-input_error'),
			$placeholder, $label;

		if (!$input.val()) {
			$placeholder = $wrapper.find('.js-modal_logon-form-input_placeholder');
			$label = $wrapper.find('.js-modal_logon-form-label');

			$label.addClass('g-hidden');
			$placeholder.removeClass('g-hidden');
		}

		if (!$error.hasClass('g-hidden')) {
			$error.addClass('g-hidden');
		}
	};

	ModalLogon.prototype.togglePlaceholder = function (e) {
		this.focusInput(e);
		this.blurInput(e);
	};

	ModalLogon.prototype.keyupInput = function (e) {
		if (e.which === 13) {
			var $form = $(e.currentTarget).closest('form');

			switch ($form[0]) {
				case this.partials.$logonForm[0]:
					this.logOn(e);
					break;
				case this.partials.$registeruserForm[0]:
					this.registerUser(e);
					break;
				case this.partials.$restorepasswordForm[0]:
					this.restorePassword(e);
					break;
				case this.partials.$linkesiaaccountForm[0]:
					this.linkEsiaAccount(e);
					break;
			}
		}
	};

	ModalLogon.prototype.logOn = function (e) {
		var request = this._req.logOn;

		if (!request || !request.readyState || request.readyState === 4) {
			var isAgreed = this.$el.find('input[name="IAgree"]').is(':checked');

			if (isAgreed) {
				var $button = e.currentTarget.tagName === 'A' ? $(e.currentTarget) : this.$el.find('.js-modal_logon-logon'),
					params = this.toObject(this.partials.$logonForm.serializeArray());

				for (var key in params) {
					if (params.hasOwnProperty(key)) {
						params[key] = encodeURIComponent(params[key]);
					}
				}

				params.RememberMe = this.$el.find('input[name="RememberMe"]').is(':checked');
				params.SystemName = 'sps';

				if (this.validate(params, 'logOn')) {
					this.setIAgreeFlag();
					this.saveSearchParams();

					showLoader(true);

					this._req.logOn = $.ajax({
						url: config.services.logOn,
						data: params,
						type: 'post',
						dataType: 'json',
						success: function (data) {
							if (data.Success) {
								var locationReload = function() {
									if (this.redirectUrl) {
										location.href = this.redirectUrl;
									}

									location.reload();
								}.bind(this);

								if (e.currentTarget.tagName === 'INPUT') {
									$(e.currentTarget).blur();
								}

								$button
									.addClass('g-hidden')
									.parent()
									.find('.js-modal_logon-logon_autorization')
									.removeClass('g-hidden')
									.find('.js-modal_logon-button-handler-spiner')
									.spin('toggler', '#99a8bf');

								if (this.isPopup) {
									if (window.opener) {
										window.opener.focus();

										if (this.redirectUrl) {
											window.opener.location.href = this.redirectUrl;
										}

										window.opener.location.reload();
									}

									window.close();
								} else if ($('.js-sj_auth').length) {
									locationReload();
								} else {
									if ($('#userExternalId').val() == data.Result.ExternalId) {
										this.hide();
										$('.b-sj_auth').removeClass('g-hidden');
									} else {
										locationReload();
									}
								}
							} else {
								hideLoader();

								this.showErrorMessages({
									messages: [data.Message]
								}, 'logOn');
							}
						}.bind(this),
						error: function () {
							hideLoader();

							var message = '';

							try {
								message = JSON.parse(xhr.responseText).Message;
							} catch (e) {}

							this.showErrorMessages({
								messages: [message]
							}, 'logOn');
						}
					});
				}
			}
		}

		return false;
	};

	ModalLogon.prototype.logOff = function () {
		$.ajax({
			url: config.services.logOff,
			type: 'post',
			dataType: 'json',
			success: function(data) {
				var result = data.Result;

				if (result.IsESIA) {
					location.href = result.Url;
				} else {
					if ((location.pathname + location.search) === result.Url) {
						location.reload();
					} else {
						location.href = result.Url;
					}
				}
			}
		});
	};

	ModalLogon.prototype.openLogOffPage = function (href) {
		if (this.isIframe) {
			var width = Math.min(800, screen.availWidth),
				height = Math.min(800, screen.availHeight),
				left = (screen.width - width) / 2,
				top = (screen.height - height) / 2;

			window.open(location.origin + '/Kad/LogOffPage' + '?href=' + encodeURIComponent(href.split('?')[0]), null, `popup=true,width=${width},height=${height},top=${top},left=${left}`);

			return false;
		}
	};

	ModalLogon.prototype.registerUser = function (e) {
		var request = this._req.registerUser;

		if (!request || !request.readyState || request.readyState === 4) {
			var isAgreed = this.$el.find('input[name="IAgree"]').is(':checked');

			if (isAgreed) {
				var params = this.toObject(this.partials.$registeruserForm.serializeArray()),
					mappedParams = {};

				for (var key in params) {
					if (params.hasOwnProperty(key)) {
						// params[key] = encodeURIComponent(params[key]);

						mappedParams[this.inputNamesMap[key] || key] = params[key];
					}
				}

				params = mappedParams;

				params.SystemName = 'sps';

				if (this.validate(params, 'registerUser')) {
					this.setIAgreeFlag();
					this.saveSearchParams();

					showLoader(true);

					this._req.logOn = $.ajax({
						url: config.services.registerUser,
						data: params,
						type: 'post',
						dataType: 'json',
						success: function (data) {
							if (data.Success) {
								this.hide();

								this.successForm = this.successForm || new this.constructor.SuccessForm;

								var locationReload = function () {
										if (this.isPopup) {
											if (window.opener) {
												window.opener.focus();

												if (this.redirectUrl) {
													window.opener.location.href = this.redirectUrl;
												} else {
													window.opener.location.reload();
												}
											}

											window.close();
										} else if (this.redirectUrl) {
											location.href = decodeURIComponent(this.redirectUrl);
										} else {
											location.reload();
										}
									}.bind(this);

								this.successForm.show('Инструкция по&nbsp;активации учетной записи отправлена на&nbsp;адрес Вашей&nbsp;электронной&nbsp;почты', {
									afterShowCallback: function () {
										setTimeout(locationReload, 10000);
									}.bind(this),
									afterHideCallback: locationReload
								});
							} else {
								this.showErrorMessages({
									messages: [data.Message]
								}, 'registerUser');
							}
						}.bind(this),
						error: function () {
							var message = '';

							try {
								message = JSON.parse(xhr.responseText).Message;
							} catch (e) {}

							this.showErrorMessages({
								messages: [message]
							}, 'registerUser');
						},
						complete: hideLoader
					});
				}
			}
		}

		return false;
	};

	ModalLogon.prototype.restorePassword = function (e) {
		var request = this._req.restorePassword;

		if (!request || !request.readyState || request.readyState === 4) {
			var params = this.toObject(this.partials.$restorepasswordForm.serializeArray());

			if (this.validate(params, 'restorePassword')) {
				showLoader(true);

				this._req.restorePassword = $.ajax({
					url: config.services.remindPassword,
					data: params,
					type: 'post',
					dataType: 'json',
					success: function (data) {
						if (data.Success) {
							var prevMode = this.prevMode;

							this.hide();

							this.successForm = this.successForm || new this.constructor.SuccessForm;

							this.successForm.show(data.Result, {
								afterHideCallback: function () {
									if (this.isBlocker) {
										this.show({
											isBlocker: this.isBlocker,
											mode: prevMode
										});
									}
								}.bind(this)
							});
						} else {
							this.showErrorMessages({
								messages: [data.Message]
							}, 'restorePassword');
						}
					}.bind(this),
					error: function (xhr) {
						var message = '';

						try {
							message = JSON.parse(xhr.responseText).Message;
						} catch (e) {
							message = xhr.responseText;
						}

						this.showErrorMessages({
							messages: [message]
						}, 'restorePassword');
					}.bind(this),
					complete: hideLoader
				});
			}
		}

		return false;
	};

	ModalLogon.prototype.linkEsiaAccount = function (e) {
		var request = this._req.linkEsiaAccount;

		if (!request || !request.readyState || request.readyState === 4) {
			var params = this.toObject(this.partials.$linkesiaaccountForm.serializeArray());

			if (this.validate(params, 'linkEsiaAccount')) {
				showLoader(true);

				this._req.linkEsiaAccount = $.ajax({
					url: config.services.linkEsiaAccount,
					data: params,
					type: 'post',
					dataType: 'json',
					success: function (data) {
						if (data.Success) {
							this.hide();

							this.successForm = this.successForm || new this.constructor.SuccessForm;

							this.successForm.show(data.Result);
						} else {
							this.showErrorMessages({
								messages: [data.Message]
							}, 'linkEsiaAccount');
						}
					}.bind(this),
					error: function (xhr) {
						var message = '';

						try {
							message = JSON.parse(xhr.responseText).Message;
						} catch (e) {
							message = xhr.responseText;
						}

						this.showErrorMessages({
							messages: [message]
						}, 'linkEsiaAccount');
					}.bind(this),
					complete: hideLoader
				});
			}
		}

		return false;
	};

	ModalLogon.prototype.validate = function (data, action) {
		var serviceRules = this.validateRules[action],
			validationFails = false,
			validationMessages = [],
			validationFields = [],
			validationFieldsMessages = {};

		if (serviceRules) {
			var keys = (function () {
					var keys = [];

					for (var key in serviceRules) {
						if (serviceRules.hasOwnProperty(key)) {
							keys.push(key);
						}
					}

					return keys;
				})();

			for (var i = 0, imax = keys.length; i < imax; i++) {
				var name = keys[i],
					validator = serviceRules[name];

				if (validator) {
					for (var j = 0, jmax = validator.rules.length; j < jmax; j++) {
						var rule = validator.rules[j],
							namesArray = name.split('.'),
							dataValue = data[name];

						if (typeof dataValue !== 'undefined') {
							var result = this.validators[rule](dataValue, data);

							if (result.status) {
								if (result.value) {
									data[name] = result.value;
								}
							} else {
								var validatorMessage = validator.message || result.message;

								if (result.fields) {
									for (var k = 0, kmax = result.fields.length; k < kmax; k++) {
										validationFieldsMessages[result.fields[k]] = validatorMessage;
									}
								} else {
									validationFieldsMessages[name] = validatorMessage;
								}

								validationMessages.push(validatorMessage);

								result.fields = result.fields || [name];

								for (var k = 0, kmax = result.fields.length; k < kmax; k++) {
									validationFields.push(result.fields[k]);
								}

								validationFails = true;

								break;
							}
						}
					}
				}
			}
		}

		this.showErrorMessages({
			messages: validationMessages,
			fields: validationFields,
			fieldsMessages: validationFieldsMessages
		}, action);

		return !validationFails;
	};

	ModalLogon.prototype.showErrorMessages = function (errors, action) {
		if (action) {
			var $form = this.partials['$' + action.toLowerCase() + 'Form'];

			if ($form && $form.length) {
				$form.find('.js-modal_logon-form-input_error').addClass('g-hidden');

				if (errors) {
					if (errors.fields) {
						for (var i = 0, imax = errors.fields.length, item; i < imax; i++) {
							item = errors.fields[i];

							if (errors.fieldsMessages && errors.fieldsMessages[item]) {
								var $input = $form.find('[name="' + item + '"]');

								if (!$input.length) {
									$input = $form.find('[data-name="' + item + '"]');
								}

								$input
									.parent()
									.find('.js-modal_logon-form-input_error')
									.text(errors.fieldsMessages[item])
									.removeClass('g-hidden');
							}
						}
					} else if (errors.messages) {
						showPageMessage({
							type:'error',
							title:'Ошибка',
							message: errors.messages[0],
							right:20
						});
					}
				}
			}
		}
	};

	ModalLogon.prototype.preventEvent = function (e) {
		e.preventDefault();

		return false;
	};

	ModalLogon.prototype.toObject = function (arr) {
		var obj = {};

		for (var i = 0, imax = arr.length; i < imax; i++) {
			obj[arr[i].name] = arr[i].value;
		}

		return obj;
	};

	ModalLogon.prototype.saveSearchParams = function () {
		var $mainColumn = $('#main-column1');

		if ($mainColumn.length) {
			var $participantsWrappers = $mainColumn.find('#sug-participants .tag'),
				$judgesWrappers = $mainColumn.find('#sug-judges .tag'),
				$courtsWrappers = $mainColumn.find('#caseCourt .tag'),
				$casesWrappers = $mainColumn.find('#sug-cases .tag'),
				$datesWrapper = $mainColumn.find('#sug-dates'),
				$activeFilterCases = $('#filter-cases').find('li.active'),
				activeFilterclass = $activeFilterCases.length && $.trim($activeFilterCases.attr('class').replace('active', '')),
				searchParams = {
					'participants': [],
					'judges': [],
					'courts': [],
					'cases': [],
					'dates': {},
					'wasSearching': !($('.b-results').hasClass('g-hidden') && $('.b-noResults').hasClass('g-hidden')),
					'withVKSInstances': $('.vksCheckClass').attr('checked'),
					'activeFilter': activeFilterclass || null
				},
				modifySearchParamsArr = function(field) {
					var arr = searchParams[field];

					if ((arr.length > 1)) {
						var firsElem = arr.splice(0, 1);

						arr.push(firsElem[0]);
					}
				},
				getInputVal = function($input) {
					var value = $input.val(),
						placeholder =  $input.attr('placeholder');

					if (placeholder && (placeholder === value)) {
						value = '';
					}

					return value;
				};

			$.each($participantsWrappers, function(i, e) {
				var $participantWrapper = $(e),
					participantName = getInputVal($participantWrapper.find('textarea')),
					participantType = $participantWrapper.find('input[type="radio"]:checked').val();

				searchParams.participants.push({
					'Name': participantName || null,
					'Type': participantType
				});
			});

			modifySearchParamsArr('participants');

			$.each($judgesWrappers, function(i, e) {
				var $input = $(e).find('input[type="text"]');
				var judgeName = getInputVal($input);
				var judgeId = $input.attr('id');

				searchParams.judges.push({
					'Name': judgeName || null,
					'Id': judgeId || null
				});
			});

			modifySearchParamsArr('judges');

			$.each($courtsWrappers, function(i, e) {
				var courtName = getInputVal($(e).find('input[type="text"]'));

				searchParams.courts.push({
					'Name': courtName || null
				});
			});

			modifySearchParamsArr('courts');

			$.each($casesWrappers, function(i, e) {
				var caseNumber = getInputVal($(e).find('input[type="text"]'));

				searchParams.cases.push({
					'Number': caseNumber || null
				});
			});

			modifySearchParamsArr('cases');

			var dateFrom = getInputVal($datesWrapper.find('.from input')),
				dateTo = getInputVal($datesWrapper.find('.to input'));

			if (dateFrom) {
				searchParams.dates['from'] = dateFrom;
			}

			if (dateTo) {
				searchParams.dates['to'] = dateTo;
			}

			$.cookie('searchCasesParams', JSON.stringify(searchParams));
		}
	};

	ModalLogon.prototype.setIAgreeFlag = function () {
		var cookieDomainMatches = location.hostname.match(/((\.)?[a-z]+\.)?[a-z]+$/);

		$.cookie('is_agree_privacy_policy', 'true', {
			expires: 365,
			path: '/',
			domain: cookieDomainMatches ? cookieDomainMatches[0] : location.hostname
		});
	};

	ModalLogon.prototype.toggleRememberMeCheckbox = function (e) {
		var isChecked = e.currentTarget.checked,
			esiaUrl = '/account/esiaauth',
			isRememberMeParam = isChecked ? 'isRemember=true' : '';

		function filter (arr) {
			var result = [];

			for (var i = 0, imax = arr.length; i < imax; i++) {
				if (arr[i]) {
					result.push(arr[i]);
				}
			}

			return result;
		}

		this.partials.$esiaLink.attr('href', filter([esiaUrl, filter([isRememberMeParam, this.esiaRedirectAddress]).join('&')]).join('?'));
	};

	ModalLogon.prototype.toggleIAgreeCheckbox = function (e) {
		var isChecked = e ? e.currentTarget.checked : this.$el.find('input[name="IAgree"]').is(':checked');

		this.$el.find('.js-modal_logon-esia, .js-modal_logon-logon, .js-modal_logon-logon_autorization, .js-modal_logon-registeruser').toggleClass('b-modal_logon-button-handler--disabled js-modal_logon-prevent_event', !isChecked);
	};

	ModalLogon.prototype.initInputNamesMap = function (e) {
		this.inputNamesMap = this.inputNamesMap || {};

		var $inputsWithoutName = $('[data-name]', this.$el);

		$inputsWithoutName.each(function (i, elem) {
			var key = createGuid(),
				name = elem.getAttribute('data-name');

			this.inputNamesMap[key] = name;

			elem.setAttribute('name', key);
		}.bind(this));
	};

	ModalLogon.SuccessForm = (function () {
		var callback = null;

		function SuccessForm () {
			this.$successForm =  $('#popup-rememberSuccess2');
			this.$forms = $(null).add(this.$successForm);
		}

		SuccessForm.prototype = {
			show: function (message, params) {
				params = params || {};

				params.afterShowCallback && params.afterShowCallback();

				if (params.afterHideCallback) {
					callback = params.afterHideCallback;
				}

				this.$successForm.show().siblings('.b-popup-block').hide();

				$('.js-remember-email', this.$successForm).html(message);

				this.bind();
			},

			close: function () {
				this.$forms.hide();

				if (callback) {
					callback();

					callback = null;
				}

				this.unbind();
			},

			bind: function () {
				var self = this;

				$('form', self.$successForm).bind('submit', function () {
					self.close();

					return false;
				});

				$('.b-popup-block__close', self.$forms).bind('click', function () {
					self.close();
				});

				$($.browser.msie ? 'body' : window).bind('keyup.success_form_esc_close', function (e) {
					if (e && e.keyCode == 27) {
						self.close();
					}
				});
			},

			unbind: function () {
				$('form', self.$successForm).unbind('submit');
				$('.b-popup-block__close', self.$forms).unbind('click');
				$($.browser.msie ? 'body' : window).unbind('keyup.success_form_esc_close');
			},
		};

		return SuccessForm;
	})();

	window.ModalLogon = new ModalLogon;
});;
$(function () {
	var Pravocaptcha = function () {
			this.template = $('#pravocaptcha_template').html();
			this._req = {};
			this.partials = {};
			this.callback = null;
			this.cancelCalback = null;
			this.isLoading = false;
			this.isAudioLoading = false;
			this.isSending = false;
			this.id = null;
			this.isCloseable = true;
			this.isShown = false;

			try {
				this.configServices = config.services;
			} catch (e) {}

			this.isOldIE = $('html').hasClass('lt-ie10');

			this.initialize();
		};

	Pravocaptcha.prototype.delegateEvents = function () {
		var self = this;

		this.$el
			.delegate('.js-pravocaptcha-close', 'click', function () {
				self.hide({
					isManual: true
				});

				return false;
			})
			.delegate('.js-pravocaptcha-update', 'click', function () {
				self.update();

				return false;
			})
			.delegate('.js-pravocaptcha-listen', 'click', function () {
				self.listen();

				return false;
			})
			.delegate('.js-pravocaptcha-input', 'input change', function () {
				self.changeInput();
			})
			.delegate('.js-pravocaptcha-input', 'keyup', function (e) {
				if (e.which === 13) {
					self.send();
				}
			})
			.delegate('.js-pravocaptcha-send', 'click', function () {
				self.send();

				return false;
			});
	};

	Pravocaptcha.prototype.initAudio = function () {
		var self = this;

		this.player = new window.Audio();

		/*this.player.addEventListener('pause', function () {
			console.log('pause');
		});

		this.player.addEventListener('playing', function () {
			console.log('playing');
		});

		this.player.addEventListener('play', function () {
			console.log('play');
		});

		this.player.addEventListener('progress', function () {
			console.log('progress');
		});

		this.player.addEventListener('ended', function () {
			console.log('ended');
		});

		this.player.addEventListener('durationchange', function () {
			console.log('durationchange', this.duration);
		});*/

		this.player.addEventListener('loadeddata', function () {
			// console.log('loadeddata', this.duration);

			self.stopAudioPreloader();

			this.play();
		});

		this.player.onerror = function () {
			self.stopAudioPreloader();
		};

		/*this.player.addEventListener('loadedmetadata', function () {
			console.log('loadedmetadata', this.duration);
		});

		this.player.addEventListener('stalled', function () {
			console.log('stalled');
		});

		this.player.addEventListener('timeupdate', function () {
			console.log('timeupdate', this.currentTime);
		});

		this.player.addEventListener('waiting', function () {
			console.log('waiting');
		});*/
	};

	Pravocaptcha.prototype.initialize = function () {
		this.$el = $('<div class="b-pravocaptcha-modal">');

		this.$modal = $('<div class="b-pravocaptcha-modal_wrapper">');

		this.$modal.appendTo('body');

		this.initializeWasm();
	};

	Pravocaptcha.prototype.render = function () {
		this.$el.html(this.template);

		this.$el.appendTo(this.$modal);

		this.partials.$popup = this.$el.find('.js-pravocaptcha');
		this.partials.$image = this.$el.find('.js-pravocaptcha-image');
		this.partials.$imageWrapper = this.partials.$image.parent();
		this.partials.$field = this.$el.find('.js-pravocaptcha-field');
		this.partials.$input = this.partials.$field.find('.js-pravocaptcha-input');
		this.partials.$description = this.partials.$field.find('.js-pravocaptcha-description');
		this.partials.$close = this.$el.find('.js-pravocaptcha-close');
		this.partials.$update = this.$el.find('.js-pravocaptcha-update');
		this.partials.$listen = this.$el.find('.js-pravocaptcha-listen');
		this.partials.$send = this.$el.find('.js-pravocaptcha-send');

		this.initTabSwitchElems();

		this.toggleCloseButton();

		this.delegateEvents();
	};

	Pravocaptcha.prototype.show = function () {
		if (!this.isShown) {
			this.isShown = true;

			this.$modal.hide();

			this.render();

			this.$modal.show();

			this.toggleEscListener(true);
			this.toggleTabListener(true);

			this.update();

		}
	};

	Pravocaptcha.prototype.remove = function () {
		this.$el.remove();

		this.isShown = false;
	};

	Pravocaptcha.prototype.hide = function (options) {
		options = options || {};

		if (this.isCloseable || options.isForce) {
			this.remove();

			this.$modal.hide();

			this.toggleEscListener();
			this.toggleTabListener();

			this.player && this.player.pause();

			if (options.isManual && this.cancelCalback) {
				this.cancelCalback();
			}
		}
	};

	Pravocaptcha.prototype.toggleEscListener = function (on) {
		var self = this;

		$($.browser.msie ? 'body' : window)[on ? 'bind' : 'unbind']('keyup.pravocaptcha_esc_close', on && function(e) {
			if (e && e.keyCode == 27) {
				self.hide({
					isManual: true
				});
			}
		});
	};

	Pravocaptcha.prototype.initTabSwitchElems = function () {
		this.tabSwitchElems = [
			this.partials.$input[0],
			this.partials.$update[0],
			this.partials.$listen[0],
			this.partials.$send[0],
		];
	};

	Pravocaptcha.prototype.toggleTabListener = function (on) {
		var self = this;

		$($.browser.msie ? 'body' : window)[on ? 'bind' : 'unbind']('keydown.pravocaptcha_tab_switch', on && function (e) {
			if (e && e.keyCode == 9) {
				var activeElement = document.activeElement,
					activeSwitchElemIndex = self.tabSwitchElems.indexOf(activeElement),
					nextActiveElement = self.tabSwitchElems[activeSwitchElemIndex + 1];

				if (!nextActiveElement) {
					nextActiveElement = self.tabSwitchElems[0];
				}

				nextActiveElement.focus();

				e.preventDefault();

				return false;
			}
		});
	};

	Pravocaptcha.prototype.execute = function (callback, cancelCalback) {
		this.callback = callback;
		this.cancelCalback = cancelCalback || null;

		this.checkRelevance();
	};

	Pravocaptcha.prototype.checkRelevance = function () {
		var self = this;

		if ($.cookie('rcid')) {
			self.callback();
		} else {
			self.checkIsNeedShow(function (isNeedShow) {
				if (isNeedShow) {
					self.show();
				} else {
					self.callback();
				}
			});
		}
	};

	Pravocaptcha.prototype.checkIsNeedShow = function (callback) {
		var self = this;

		if (!self._req.checkIsNeedShow) {
			self._req.checkIsNeedShow = $.ajax({
				url: self.configServices.checkIsNeedShowCaptcha,
				type: 'get',
				dataType: 'json',
				cache: false,
				success: function(data) {
					callback(data && data.Result);
				},
				error: function () {
					callback(true);
				},
				complete: function () {
					delete (self._req.checkIsNeedShow);
				}
			});
		}
	};

	Pravocaptcha.prototype.getId = function (callback) {
		var self = this;

		this.startImagePreloader();

		this.id = null;

		this._req.getId = $.ajax({
			url: this.configServices.getCaptchaId,
			type: 'get',
			dataType: 'json',
			cache: false,
			success: function(data) {
				self.id = data.Result; // 'cf952fde-d05f-4f6c-95a6-006db9aa8d6e'; // https://jira.parcsis.org/browse/KAD-12378
			},
			complete: function (xhr, status) {
				if (status === 'success') {
					if (callback) {
						callback();
					} else {
						self.stopImagePreloader();
					}
				} else {
					self.stopImagePreloader();
				}
			}
		});
	};

	Pravocaptcha.prototype.setImage = function () {
		if (this.id) {
			var self = this,
				image = this.partials.$image[0];

			image.src = this.configServices.getCaptchaImage + this.id;

			image.onload = function () {
				self.stopImagePreloader();

				self.partials.$image.show();

				self.partials.$input.focus();
			};

			image.onerror = function () {
				self.stopImagePreloader();
			};
		}
	};

	Pravocaptcha.prototype.update = function () {
		if (!this.isLoading) {
			var self = this;

			this.player && this.player.pause();

			this.clearDescription();
			this.partials.$image.hide();
			this.partials.$input
				.val('')
				.trigger('change');

			this.getId(function () {
				self.setImage();
			});
		}
	};

	Pravocaptcha.prototype.startImagePreloader = function () {
		this.startPreloader(this.partials.$imageWrapper, 'isLoading');
	};

	Pravocaptcha.prototype.stopImagePreloader = function () {
		this.stopPreloader(this.partials.$imageWrapper, 'isLoading');
	};

	Pravocaptcha.prototype.startAudioPreloader = function () {
		this.startPreloader(this.partials.$listen, 'isAudioLoading');
	};

	Pravocaptcha.prototype.stopAudioPreloader = function () {
		this.stopPreloader(this.partials.$listen, 'isAudioLoading');
	};

	Pravocaptcha.prototype.startPreloader = function ($context, loadingFlagName) {
		if (!this[loadingFlagName]) {
			$context.addClass('b-preloader');

			this[loadingFlagName] = true;

			if (this.isOldIE) {
				var $preloaderSpin = $context.find('.js-preloader-spin'),
					$preloaderCircular = $preloaderSpin.find('.circular'),
					$preloaderPath = $preloaderSpin.find('.path'),
					self = this;

				function rotatePreloader () {
					if (self[loadingFlagName]) {
						$({deg: 0}).animate({deg: 360}, {
							duration: 2000,
							step: function(now) {
								$preloaderCircular.css({
									transform: 'rotate(' + now + 'deg)',
									msTransform: 'rotate(' + now + 'deg)'
								});
							},
							easing: 'linear',
							complete: function () {
								rotatePreloader();
							}
						});
					}
				}

				function dashPreloader () {
					if (self[loadingFlagName]) {
						$({
							dasharray: 1,
							dashoffset: 0
						}).animate({
							dasharray: 89,
							dashoffset: -35
						}, {
							duration: 750,
							step: function(now, fx) {
								if (fx.prop === 'dasharray') {
									$preloaderPath.css({
										strokeDasharray: now + ', 200'
									});
								} else if (fx.prop === 'dashoffset') {
									$preloaderPath.css({
										strokeDashoffset: now + 'px'
									});
								}
							},
							complete: function () {
								$({
									dashoffset: -35
								}).animate({
									dashoffset: -124
								}, {
									duration: 750,
									step: function(now) {
										$preloaderPath.css({
											strokeDashoffset: now + 'px'
										});
									},
									complete: function () {
										dashPreloader();
									}
								});
							}
						});
					}
				}

				rotatePreloader();
				dashPreloader();
			}
		}
	};

	Pravocaptcha.prototype.stopPreloader = function ($context, loadingFlagName) {
		$context.removeClass('b-preloader');

		if (loadingFlagName) {
			this[loadingFlagName] = false;
		}
	};

	Pravocaptcha.prototype.listen = function () {
		if (this.id) {
			var self = this,
				src = this.configServices.getCaptchaSound + this.id + '.mp3'; // 'http://ol2.mp3party.net/online/1768/1768268.mp3'

			if (!this.player) {
				this.initAudio();
			}

			this.player.pause();

			if (this.player._src === src) {
				if (this.player.currentTime) {
					this.player.currentTime = 0;
				}

				this.player.play();
			} else if (window.Blob) {
				this.startAudioPreloader();

				var xhr = this._req.getAudio = new XMLHttpRequest();

				xhr.onload = function () {
					if (this.status === 200) {
						var blob = new Blob([this.response], {type : 'audio/mpeg'}),
							URL = window.URL || window.webkitURL,
							audioUrl = URL.createObjectURL(blob);

						if (self.player.src) {
							URL.revokeObjectURL(self.player.src);
						}

						self.player._src = src;
						self.player.src = audioUrl;
					} else {
						self.stopAudioPreloader();

						self.showMessage('Ошибка ' + this.status);
					}
				};

				xhr.open('GET', src, true);
				xhr.responseType = 'arraybuffer';
				xhr.send();
			} else {
				this.startAudioPreloader();

				this.player.src = this.player._src = src;
			}
		}
	};

	Pravocaptcha.prototype.changeInput = function () {
		this.partials.$field.toggleClass('b-pravocaptcha-field--value', !!this.partials.$input.val());
	};

	Pravocaptcha.prototype.send = function () {
		if (!this.isLoading && !this.isSending) {
			this.isSending = true;

			var self = this,
				blockPopupStyleClass = 'b-pravocaptcha--block',
				waitStyleClass = 'g-wait';

			this.clearDescription();

			this.partials.$popup.addClass(waitStyleClass);
			//this.partials.$popup.addClass(blockPopupStyleClass);

			this._req.send = $.ajax({
				url: this.configServices.checkCaptcha,
				type: 'get',
				dataType: 'json',
				data: {
					id: this.id,
					text: this.partials.$input.val().replace(/^\s*(\S*)\s*$/, '$1')
				},
				success: function(data) {
					if (data.Result) {
						self.callback && self.callback(self.id);

						self.callback = null;

						self.hide({
							isForce: true
						});
					} else {
						self.update();
						self.setDescription('Введен неверный код, картинка обновлена');
					}
				},
				complete: function () {
					self.isSending = false;

					self.partials.$popup.removeClass(waitStyleClass);
					//self.partials.$popup.removeClass(blockPopupStyleClass);
				}
			});
		}
	};

	Pravocaptcha.prototype.setDescription = function (text) {
		this.partials.$description.text(text);
	};

	Pravocaptcha.prototype.clearDescription = function () {
		this.setDescription('');
	};

	Pravocaptcha.prototype.removeCloseAbility = function () {
		this.toggleCloseAbility(false);
	};

	Pravocaptcha.prototype.toggleCloseAbility = function (isCloseable) {
		this.isCloseable = isCloseable !== undefined ? isCloseable : !this.isCloseable;
	};

	Pravocaptcha.prototype.toggleCloseButton = function () {
		this.partials.$close.toggle(this.isCloseable);
	};

	Pravocaptcha.prototype.initializeWasm = function () {
		var self = this;
		var isValid;

		try {
			isValid = (typeof window.WebAssembly !== 'undefined') && (typeof window.Promise !== 'undefined') && (typeof window.Promise.prototype['finally'] !== 'undefined');  // window.Promise.prototype['finally'] - ie8
		} catch (e) {
			isValid = false;
		}

		if (isValid) {
			self.initializeFp();

			var checkRelevance = self.checkRelevance;

			self.checkRelevance = function () {
				if (!self._req.setFpWaiting) {
					self._req.setFpWaiting = true;

					self._req.setFp.finally(function () {
						self._req.setFpWaiting = false;

						if ($.cookie('wasm')) {
							checkRelevance.call(self);
						} else {
							self.loadWasm(function () {
								checkRelevance.call(self);
							});
						}
					});
				}
			};
		} else {
			var cookieDomainMatches = location.hostname.match(/\..*\..*$/);

			$.cookie('wasm', '68D5834C6D9AE0EBB645C93DA0272857', {
				path: '/',
				domain: cookieDomainMatches ? cookieDomainMatches[0] : location.hostname
			});
		}
	};

	Pravocaptcha.prototype.loadWasm = function (callback) {
		var self = this;

		self.initTextEncoder(function () {
			if (!self._req.loadWasm && !self._req.checkIsNeedShow) {
				self._req.loadWasm = $.ajax({
					url:  self.configServices.getCaptchaWasm,
					cache: false,
					dataType: 'script',
					success: function () {
						if (window.wasm) {
							var wasmPromise = new Promise(function (resolve) {
									window.onwasm = function () {
										resolve();
									};
								});

							window.wasm['default'](self.configServices.getCaptchaWasmBG + '?_=' + (new Date).getTime()); // window.wasm['default'] - ie8

							wasmPromise.then(function () {
								delete (self._req.loadWasm);
								callback();
							});
						} else {
							delete (self._req.loadWasm);
							callback();
						}
					},
					error: function () {
						delete (self._req.loadWasm);
						callback();
					}
				});
			}
		});
	};

	Pravocaptcha.prototype.initializeFp = function () {
		var self = this;

		self._req.setFp = new Promise(function (resolve, reject) {
			self.initTextEncoder(function () {
				$.ajax({
					url: '/Content/Static/js/common/fp.js?_=1705670688006',
					cache: true,
					dataType: 'script',
					success: function () {
						window.fp.default('/Content/Static/js/common/fp_bg.wasm?_=1705670688006').then(function () {
							window.fp.get().then(function (data) {
								resolve(data);
							}, function (err) {
								reject(err);
							});
						});
					},
					error: function (err) {
						reject(err);
					}
				});
			});
		});
	};

	Pravocaptcha.prototype.initTextEncoder = function (callback) {
		var self = this;

		if (!self._req.loadEncoding) {
			if ((typeof window.TextEncoder === 'undefined') || (typeof window.TextDecoder === 'undefined')) {
				self._req.loadEncoding = $.ajax({
					url: '/Content/Static/js/libs/encoding.js',
					dataType: 'script',
					complete: function () {
						delete (self._req.loadEncoding);
						callback();
					}
				});
			} else {
				callback();
			}
		}
	};

	Pravocaptcha.prototype.showMessage = function (title, message) {
		try {
			var notifyView = Common.get('Notify').view;

			if (notifyView) {
				this.showMessage = function (title, message) {
					notifyView.show({
						type: 'error',
						title: title || '',
						message: message || '',
					});
				};
			}
		} catch (e) {
			try {
				if (showPageMessage) {
					this.showMessage = function (title, message) {
						showPageMessage({
							type:'error',
							title: title || '',
							message: message || '',
							right: 20
						});
					};
				}
			} catch (e) {
				this.showMessage = function (title, message) {
					console.error({
						title: title || 'Ошибка',
						message: message || 'Произошла ошибка, сделайте скриншот и обратитесь в техническую поддержку cases@pravo.ru',
					});
				};
			}
		}

		this.showMessage(title, message);
	};

	window.pravocaptcha = new Pravocaptcha;
});;
!function(e,n,o){function i(e){return e}function t(e){return decodeURIComponent(e.replace(r," "))}var r=/\+/g,s=e.cookie=function(o,r,u){if(undefined!==r){if(u=e.extend({},s.defaults,u),null===r&&(u.expires=-1),"number"==typeof u.expires){var a=u.expires,p=u.expires=new Date;p.setDate(p.getDate()+a)}return r=s.json?JSON.stringify(r):String(r),n.cookie=[encodeURIComponent(o),"=",s.raw?r:encodeURIComponent(r),u.expires?"; expires="+u.expires.toUTCString():"",u.path?"; path="+u.path:"",u.domain?"; domain="+u.domain:"","; samesite="+(u.sameSite||"none"),"; secure"].join("")}for(r=s.raw?i:t,u=n.cookie.split("; "),a=0;p=u[a]&&u[a].split("=");a++)if(r(p.shift())===o)return o=r(p.join("=")),s.json?JSON.parse(o):o;return null};s.defaults={},e.removeCookie=function(n,o){return null!==e.cookie(n)&&(e.cookie(n,null,o),!0)}}(jQuery,document);;
function initFilters() {
	return '#sug-participants textarea, #sug-judges input[type=text], #caseCourt input[type=text], #sug-cases input[type=text], #sug-dates .from input[type=text], #sug-dates .to input[type=text]';
}

//;(function() {
	//----------- таблица дел ----------------
	function setWidthOfTh(){ //Подгоняет ширину ячеек у заголовочной таблицы
		var plaintiffTdWidth = parseInt(($('#b-cases').width() - $('#b-cases thead th').eq(0).width()-$('#b-cases thead th').eq(1).width()-$('#b-cases thead th').eq(2).width()-16*5)/2);
		$('#b-cases thead th').eq(3).width(plaintiffTdWidth);
	//	$('#b-cases-head').parent().width($('#b-cases').width());
	}
	function setWidth(targetElem,initialElem,/*учет паддингов*/plus){
		if(!plus) plus = 0;
		$(targetElem).width($(initialElem).width()+plus);
	}

	function setWidthColumn() {
		if ($('#b-cases-theader').css('display') == 'table') {
			var headerColumns = $('#b-cases-theader').find('th'),
				cols = $('#b-cases').find('col');

			for (var i = 0, max = cols.length; i < max; i++) {
				$(cols[i]).css('width', i === (max - 1) ? 'auto' : $(headerColumns[i]).css('width'));
			}
		}
	}

	function counterPosition() {
		var elem = $('.b-totalcases'),
			container = $(elem).parent(),
			containerHeight = $(container).height(),
			childs = $(container).children(),
			marginTopElement = 0;
		$(childs).each(function() {
			marginTopElement += returnBlockHeight($(this));
			marginTopElement += parseInt($(this).css('marginTop')) + parseInt($(this).css('marginBottom'));
		});

		if (marginTopElement > containerHeight) {
			$(elem).css({'position':'static', 'padding-left': '', 'padding-right': ''});
		} else {
			$(elem).css({'position':'absolute', 'padding-left': '18px'});
		}
	}

	function checkPravocaptchaCallback() {}

	function doSearchRequest(page){
		checkPravocaptchaCallback = function (token) {
			setColumnHeight();

			var info = returnRequestInfo(page);

			if (!info) {
				return false;
			}

			loading($('#main-column2 .b-case-loading .loading'), 12);

			globals.filterRequest = $.ajax({
				type:"post",
				cache : false,
				url: config.services.getInstances,
				//dataType: "json",
				data: info,
				contentType: "application/json",
				beforeSend: function (xhr) {
					xhr.setRequestHeader('x-date-format', 'iso');

					if (token) {
						xhr.setRequestHeader('RecaptchaToken', token);
					}
				},
				success: function (result) {
					var $cases,
						totalCount,
						$results = $('.b-results'),
						$noResults = $('.b-noResults', '#main-column2');

					/* Задача - http://jira.parcsis.org/browse/VS-11842
					* Решение - http://stackoverflow.com/questions/7267014/ie9-table-has-random-rows-which-are-offset-at-random-columns
					*/
					result = result && $.trim(result).replace(/>[ \t\r\n\v\f]*</g, '><');

					$cases = $('#b-cases');

					$cases.html(result);

					totalCount = parseInt($('#documentsTotalCount').val(), 10);

					if (totalCount) {
						$('#totalCount').text(totalCount);

						$noResults.addClass('g-hidden');

						reDrawPages({
							linesPerPage: parseInt($('#documentsPageSize').val(), 10),
							page:  parseInt($('#documentsPage').val(), 10),
							pagesCount:  parseInt($('#documentsPagesCount').val(), 10),
							totalCount: totalCount
						});

						$results
							.removeClass('g-hidden')
							.find('#table')
							.scrollTop(0);

						if ($('.more', '#b-cases tbody tr').length) {
							showHideEntities($('.b-button', '#b-cases tbody tr'));
						}

						$('.b-rollover').remove();

						$('#b-cases span.js-rollover').each(function() {
							var $this = $(this),
								cell = $this.closest('td'),
								cellIndex = cell.index(),
								row = cell.closest('tr'),
								html = $('.js-rolloverHtml', this).html();

							$this.attachRollover({
								vertical: cellIndex >= 2,
								html: html
							});
						});

						typeSwitcher($('.b-type-switcher'));

						if ($('#b-footer-pages ul li').length == 4) {
							$('#b-footer-pages ul').hide();
						} else {
							$('#b-footer-pages ul').show();
						}

						$('#contentHeader .h2').hide();
						$('.b-found-total').text('Найдено '+ totalCount + ' дел').show();
						$('.b-feedback').animate({'opacity':'0'}, 1000);
						$('.b-feedback').hide();

						try {
							if (ga) {
								ga('send', 'pageview', '/Kad/Search');
							}
						} catch(err) {}

						//if (yaCounter13493410) {
						//    yaCounter13493410.hit('/Kad/Search');
						//}
					} else {
						var court = $('input.js-input', '#caseCourt').valEx(),
							caseNumber = $('div.tag input', '#sug-cases').eq(0).valEx();

						$results.addClass('g-hidden');

						$noResults.removeClass('g-hidden');

						new NoResults({
							$court: $('.b-combobox', '#caseCourt').clone(),
							caseNumber: caseNumber,
							container: $noResults,
							request: info
						});

						reDrawPages({
							totalCount: 0
						});

						$('#contentHeader .h2').show();
						$('.b-found-total').hide();
						$('.b-feedback').show();
						$('.b-feedback').animate({'opacity':'1'}, 1000);
					}
				},
				complete: function() {
					highlightFound({filters:$('#sug-participants textarea')});
					globals.filterRequest = null;
					hideLoading();
					stateOfButton();
					setColumnHeight();
					setWidthColumn();
					//$('#table').scrollTo('0%',300);
				},
				error: function (xhr) {
					ajaxSetupError(xhr);

					$('.b-case-blank').show();
				}
			}); //close $.ajax
		};

		Common.executePravocaptcha(checkPravocaptchaCallback);
	}

	function returnRequestInfo(page, returnObject){
		var info = {};

		info.Page = parseInt(page, 10) || 1;
		info.Count = 25;

		var groupByCategory;
		var $active = $('#filter-cases li.active').eq(0);
		if($active){
			if($active.hasClass('administrative')){
				groupByCategory = 'A';
			}
			if($active.hasClass('bankruptcy')){
				groupByCategory = 'B';
			}
			if($active.hasClass('civil')){
				groupByCategory = 'G';
			}
		}

		if (groupByCategory) {
			info.CaseType = groupByCategory;
		}


		var $courts = $('#caseCourt .js-select'),
			courtsArray = [];

		$.each($courts, function() {
			var $select = $(this),
				$options = $select.children('option'),
				$input = $select.parent().find('.js-input'),
				inputVal = $input.val();

			if (inputVal) {
				$.each($options, function() {
					var $option = $(this);

					if ($option.text() == inputVal) {
						courtsArray.push($option.val());
					}
				});
			}
		});

		/*if (globals.isVasEnteredInKad) {
			if (courtsArray) {
				for (var i = 0, max = courtsArray.length; i < max; i++) {
					if (globals.isVasEnteredInKad && (courtsArray[i] !== 'VAS')) {
						delete globals.isVasEnteredInKad;
					}
				}
			} else {
				delete globals.isVasEnteredInKad;
			}
		}*/

		info.Courts = courtsArray;

	//	var dates = $('#selected-dates').val() || '';
	//	dates = dates.replace(/(\d{1,2})\.(\d{1,2})\.(\d{2,4})/g, '$3.$2.$1').match(/\d{2,4}\.\d{1,2}\.\d{1,2}/g) || ['',''];
	//	dates[0] = (dates[0] || '2000.01.01').split('.');
	//	dates[1] = (dates[1] || '2030.01.01').split('.');

	//	info.DateFrom = Common.date.returnDotNetDate(
	//		Common.date.returnDateUTC(dates[0][0],dates[0][1],dates[0][2])
	//	);
	//	info.DateTo = Common.date.returnDotNetDate(
	//		Common.date.returnDateUTC(dates[1][0],dates[1][1],dates[1][2], 23, 59, 59)
	//	);

		var dates = ($('#selected-dates').val() || '').split(' - ');

		if (dates[0] && !checkDate(dates[0]) || dates[1] && !checkDate(dates[1])) {
			showPageMessage({
				type: 'error',
				title: 'Ошибка',
				message: 'Введена неверная дата',
				right: 20
			});

			return false;
		}

		if (dates[0]) {
			info.DateFrom = dates[0].replace(/(\d{1,2})\.(\d{1,2})\.(\d{2,4})/g, '$3-$2-$1') + 'T00:00:00' || ['', '']; //'2000-01-01T00:00:00'
		} else {
			info.DateFrom = null;
		}

		if (dates[1]) {
			info.DateTo = dates[1].replace(/(\d{1,2})\.(\d{1,2})\.(\d{2,4})/g, '$3-$2-$1') + 'T23:59:59' || ['', '']; //'2000-01-01T00:00:00'
		} else {
			info.DateTo = null;
		}

		var tags = 'Sides,Judges,CaseNumbers'.split(','); //названия тегов
		var groups = 'sug-participants,sug-judges,sug-cases'.split(',');

		for(j in tags){
			var tag = tags[j];
			info[tag] = [];
			var field;
			if ($('#' + groups[j]+' input[type=text]').length ) {
				field = $('#' + groups[j] + ' input[type=text]');
			} else {
				field = $('#' + groups[j] + ' textarea');
			}
			field.each(function(){
				var $currentField = $(this);
				if(!$currentField.hasClass('g-ph')) {
					if (tag == "Sides") {
						info[tag].push({
							Name: $currentField.valEx(),
							Type: parseInt($currentField.closest('.tag').find('.b-type-switcher .selected input').val(), 10),
							ExactMatch: $currentField.data('exactmatch') ? true : false
						});
					} else if (tag == 'Judges') {
						var judgeId = $currentField.attr('id');

						// Тип судьи не является критерием поиска
						info[tag].push({
							JudgeId: judgeId,
							Type: -1 //$currentField.closest('.tag').find('.b-type-switcher .selected input').val() || 1
						});
					} else {
						info[tag].push($currentField.valEx());
					}
				}
			});
		}

		info.WithVKSInstances = $('.vksCheckClass').attr('checked');

		/*if (globals.isVasEnteredInKad) {
			info.InstanceLevel  = 1;
		}*/

		return returnObject ? info : $.toJSON(info);
	}

	function highlightFound(params){
		params = params || {};
		var colors = 'yellow,blue,green'.split(',');
		var colorId = 0;
		params.filters = params.filters || $('#sug-participants textarea');
		$(params.filters).each(function(){
			var stringToHighlight = $.trim($(this).valEx()).replace('=','');
			if (stringToHighlight) {
				$('#b-cases').find('td.plaintiff, td.respondent').highlight(stringToHighlight, colors[colorId]);
				(colorId == colors.length - 1) ? colorId = 0 : colorId++;
			}
		});
	}

	function getCookieSideInfo() {
		var sideName = $.cookie('sideCardName'),
			typeFilter = $.cookie('sideCardNameTypeFilter'),
			$filter, $typeFilter;

		if (sideName || typeFilter) {
			if (sideName) {
				$('#sug-participants textarea')
					.val(sideName)
					.removeClass('g-ph')
					.trigger('keyup');
			}

			if (typeFilter) {
				$filter = $('#filter-cases');

				switch (typeFilter) {
					case 'А' :
						$typeFilter = $filter.find('.administrative');
						break
					case 'Б' :
						$typeFilter = $filter.find('.bankruptcy');
						break
					case 'Г' :
						$typeFilter = $filter.find('.civil');
						break
				}

				$typeFilter.addClass('active');
			}

			$('#b-form-submit').trigger('click', [true]);
		}
	}

	function setSavedSearchCasesParams() {
		if ($.cookie('searchCasesParams')) {
			if ($('#userExternalId').val()) {
				var $mainColumn = $('#main-column1');

				if ($mainColumn.length) {
					var $datesWrapper = $mainColumn.find('#sug-dates'),
						searchParams = JSON.parse($.cookie('searchCasesParams')),
						participants = searchParams.participants,
						judges = searchParams.judges,
						courts = searchParams.courts,
						cases = searchParams.cases,
						dates = searchParams.dates,
						activeFilter = searchParams.activeFilter;

					for (var i = 0, max = participants.length; i < max; i++) {
						var participant = participants[i],
							$participantWrapper = $mainColumn.find('#sug-participants .tag:first');

						if (participant.Name) {
							$participantWrapper
								.find('textarea')
								.val(participant.Name)
								.removeClass('g-ph');
						}

						$participantWrapper
							.find('.switcher-container')
							.click()
							.find('input[type="radio"][value="' + participant.Type + '"]')
							.closest('li')
							.click();

						if (i !== (max - 1)) {
							addCaseTags($participantWrapper, $participantWrapper.find('textarea').attr('placeholder'), true);
						}
					}

					for (var i = 0, max = judges.length; i < max; i++) {
						var judge = judges[i],
							$judgeWrapper = $mainColumn.find('#sug-judges .tag:first');

						if (judge.Name) {
							$judgeWrapper
								.find('input[type="text"]')
								.val(judge.Name)
								.attr('id', judge.Id)
								.removeClass('g-ph');
						}

						if (i !== (max - 1)) {
							addCaseTags($judgeWrapper, $judgeWrapper.find('input[type="text"]').attr('placeholder'), true);
						}
					}

					for (var i = 0, max = courts.length; i < max; i++) {
						var court = courts[i],
							$courtWrapper = $mainColumn.find('#caseCourt .tag:first'),
							$input = $courtWrapper.find('input[type="text"]'),
							$select =  $courtWrapper.find('select');

						if (court.Name) {
							$input
								.val(court.Name)
								.removeClass('g-ph');
						}

						$.each($select.find('option'), function(index, option) {
							var $option = $(option);

							if ($option.text() === $input.val()) {
								$option.attr('selected', true);
								$select.closest('.js-b-combobox').data('combobox').selected = index;
							}
						});

						if (i !== (max - 1)) {
							addCaseTags($courtWrapper, $courtWrapper.find('input[type="text"]').attr('placeholder'), true);
						}

					}

					for (var i = 0, max = cases.length; i < max; i++) {
						var currentCase = cases[i],
							$caseWrapper = $mainColumn.find('#sug-cases .tag:first');

						if (currentCase.Number) {
							$caseWrapper
								.find('input[type="text"]')
								.val(currentCase.Number)
								.removeClass('g-ph');
						}

						if (i !== (max - 1)) {
							addCaseTags($caseWrapper, $caseWrapper.find('input[type="text"]').attr('placeholder'), true);
						}
					}


					if (dates.from) {
						$datesWrapper
							.find('.from input')
							.val(dates.from)
							.removeClass('g-ph');
					}

					if (dates.to) {
						$datesWrapper
							.find('.to input')
							.val(dates.to)
							.removeClass('g-ph');
					}

					if (searchParams.wasSearching) {
						$('.vksCheckClass').attr('checked', searchParams.withVKSInstances);

						if (activeFilter) {
							$('#filter-cases')
								.find('.' + activeFilter)
								.click();
						} else {
							$('#b-form-submit').click();
						}
					}
				}
			}
		}

		$.cookie('searchCasesParams', null);
	}

	$(document).ready(function(){ //=================== ready =========================
		initBrowsersPopup();
		if($('.more', '#b-cases tbody tr').length){
			showHideEntities($('.b-button', '#b-cases tbody tr'));
		}

		if(!$('#sug-cases input, #sug-participants textarea').hasClass('g-ph')){
			$('#sug-cases input, #sug-participants textarea').val('');
		}
		$('#b-form-submit').click(function(e, isVKSInstances) {
			stateOfButton();

			if($(this).hasClass('b-form-submit_noactive')) {
				return false;
			}

			if (!globals.filterRequest) {
				!isVKSInstances && $('#filter-cases li').removeClass('active');//Сброс фильтра при новом поиске
				if (!$(this).hasClass("no-kad-search")) {
					doSearchRequest(1);
				}
			}
		});
		$('#b-footer-pages #pages a').live('click',function(){
			if (!globals.filterRequest) {
				var $pageLink = $(this),
					match = $pageLink.attr('href').match(/#page([0-9]+)$/);

				//если список загружен аяксом
				if(match && !$pageLink.parent('.active').length){
					var page = match[1];
					doSearchRequest(page);
				}
			}

			return false;
		});

		//переключение страниц
		$($.browser.msie ? window.document : window).keydown(function(e){
			if (!globals.filterRequest) {
				if(e.ctrlKey == true && /^37$|^39$/.test(e.keyCode)){
					var aArr;

					if (e.keyCode === 37) {
						aArr = $('li.larr a')[0];
					} else if (e.keyCode === 39) {
						aArr = $('li.rarr a')[0];
					}

					if (aArr) {
						var match = $(aArr).attr('href').match(/#page([0-9]+)$/);

						if(match) {
							var page = match[1];
								doSearchRequest(page);
						}
					}
				}
			}
		});

		//$(window).resize();//?????


		setTimeout(function(){
				setColumnHeight();
				showHideCalendar();
				setWidthColumn();
				counterPosition();
			},1000
		);
		$(window).resize(function() {
			setTimeout(function () {
				setWidthColumn();
				setColumnHeight();
				showHideCalendar();
				counterPosition();
			}, 0);
		});

		var $mainColumn1 = $('#main-column1'),
			$comboboxBlocks = $mainColumn1.find('.js-b-combobox'),
			comboboxes = [];

		$.each($comboboxBlocks, function (index, block) {
			comboboxes.push($(block).data('combobox'));
		});

		$mainColumn1
			.resize(function() {
				counterPosition();
			})
			.bind('scroll', function () {
				for (var i = 0, max = comboboxes.length; i < max; i++) {
					var currentCombobox = comboboxes[i];

					if (currentCombobox.$suggest.is(':visible')) {
						currentCombobox.setSuggestPosition();
					}
				}
			});


		$('.tag input[type=text], .tag textarea, #sug-dates input[type=text]')
			.bind('keypress', function(e, triggerParams) {
				triggerParams = triggerParams || {};

				if((e.which === 13 || (triggerParams.which === 13)) && $('#b-suggest').css('display') != 'block') {
					if (e.ctrlKey == true && $(this).parent().find('.add').length > 0) {
						addCaseTags($(this).parent(), $(this).attr('placeholder'));
					} else {
						$(this).blur();
						stateOfButton();

						if ($('#b-form-submit').hasClass('b-form-submit_noactive')) {
							return false;
						}
					}

					return false;
				}
			})
			.bind('keypress.kad_search', function(e, triggerParams) {
				triggerParams = triggerParams || {};

				if((e.which === 13 || (triggerParams.which === 13)) && $('#b-suggest').css('display') != 'block') {
					if (!(e.ctrlKey == true && $(this).parent().find('.add').length > 0)) {
						if (!globals.filterRequest) {
							doSearchRequest(1);
						}
					}

					return false;
				}
			});

		stateOfButton();

		$('.tag textarea').TextAreaExpander(15);

		$('#filter-cases li').click(function(){
			if (!globals.filterRequest) {
				if($(this).hasClass('active')){
					$(this).removeClass('active');
				}
				else{
					$(this).addClass('active').siblings().removeClass('active');
				}

				stateOfButton();

				if($('#b-form-submit').hasClass('b-form-submit_noactive')) return false;

				doSearchRequest(1);
			}

			return false;
		});

		/*if (globals.isVasEnteredInKad) {
			doSearchRequest(1);
		}*/

		/* End Переключение категорий
		 *********************************************************/

		if ($('#contentHeader .js-checkbox').checkbox) {
			$('#contentHeader .js-checkbox')
				.checkbox({
					cls: 'ui-checkbox-fake',
					empty: '/Content/img/t/1x1.gif?v=1'
				})
				.click(function(e) {
					if (!globals.filterRequest) {
						setTimeout(function() {
							$('#b-form-submit').trigger('click', true);
						}, 1);
					} else {
						return false;
					}
				});
		}

		$('html').css('overflowY', 'hidden');

		$('#contentHeader .js-legend-checkbox-trigger').bind('click', function() {
			$('#contentHeader .js-legend-checkbox')
				.find('.js-checkbox')
				.trigger('click');
		});

		getCookieSideInfo();

		!!$.cookie('sideCardName') && $.cookie('sideCardName', null); // после того, как получили информацию из cookie, сбрасываем участника дела KAD-3180

		setSavedSearchCasesParams();

	//	//попап для ссылки на андроид-приложение
	//	$('#androidApplication').live('click.popup', function() {
	//		if (navigator.userAgent && /Android/.test(navigator.userAgent)) {//телефон
	//			return true;
	//		} else {//настольный компьютер и др
	//			new AlertDialog({
	//				message: '<p class="g-margins">Чтобы скачать приложение используйте QR-код:</p>' +
	//					'<p><img src="/i/c/qr-code-android.png" alt=""/></p>'
	//			});
	//			return false;
	//		}
	//	})

	});
//})();
;
$(function () {
	var $document = $(document),
		$body = $('body'),
		now = new Date();

	function SpecialNotification() {
		var $specialNotificationTemplate = $('#special_notification_template');

		if (window.Handlebars) {
			var $container = $('<div>');

			$container.html(Handlebars.compile($specialNotificationTemplate.html())());

			this.$modal = $($container.children()[0]);
		} else {
			this.$modal = $specialNotificationTemplate.tmpl();
		}

		this.$closeButtons = this.$modal.find('.js-special_notification-close, .js-special_notification-popup-link');
	}

	SpecialNotification.prototype.show = function () {
		$body.append(this.$modal);

		this.bindEvents();

		var cookieDomainMatches = location.hostname.match(/((\.)?[a-z]+\.)?[a-z]+$/);

		$.cookie('special_notification_shown', 'true', {
			expires: new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 8),
			path: '/',
			domain: cookieDomainMatches ? cookieDomainMatches[0] : location.hostname
		});

		this.isShown = true;
	};

	SpecialNotification.prototype.close = function () {
		this.$modal.remove();

		this.unbindEvents();
	};

	SpecialNotification.prototype.bindEvents = function () {
		var self = this;

		$document.bind('keydown.close_special_notification', function (e) {
			if (e.which === 27) {
				self.close();
			}
		})

		this.$closeButtons.bind('click.close_special_notification', function () {
			self.close();
		});
	};

	SpecialNotification.prototype.unbindEvents = function () {
		$document.unbind('keydown.close_special_notification');
		this.$closeButtons.unbind('click.close_special_notification');
	};

	window.kadSpecialNotification = new SpecialNotification;

	function showNotification () {
		if (now < (new Date(Date.UTC(2020, 5, 26, 9))) && !$.cookie('special_notification_shown')) {
			kadSpecialNotification.show();
		}
	}

	if (window.Guard) {
		setTimeout(function () {
			if (window.Guard.User.id) {
				showNotification();
			}
		}, 0);
	} else {
		showNotification();
	}
});;
$(function () {
	var alarmTitle = $('#alarm_title').val(),
		alarmMessage = $('#alarm_message').val(),
		alarmServiceId = $('#alarm_service_id').val(),
		$alarmIsHiddenLink = $('#alarm_is_hidden_link'),
		alarmIsHiddenLink = !!$alarmIsHiddenLink.length && $alarmIsHiddenLink.val().toLowerCase() === 'true',
		$document, $notification, $closeButton;

	if (!(window.kadSpecialNotification && window.kadSpecialNotification.isShown)) {
		if (alarmMessage || alarmTitle) {
			var notificationCookie = $.cookie('Notification_' + alarmServiceId);

			if (notificationCookie) {
				if (/_shown$/.test(notificationCookie)) {
					return;
				} else {
					var expireTimeStamp = notificationCookie.match(/_(\d+)$/)[1],
						expireDays = Math.floor((expireTimeStamp - (new Date)) / (1000*60*60*24)) + 2;

					 $.cookie('Notification_' + alarmServiceId, notificationCookie + '_shown', {
						 expires: expireDays
					 });
				}
			}

			$document = $(document);

			alarmMessage = unescape(alarmMessage).replace(/\n/gmi, '<br />');

			$notification = $('#promo_notification_template').tmpl({
				title: alarmTitle,
				message: alarmMessage,
				isHiddenLink: alarmIsHiddenLink
			});

			$closeButton = $notification.find('.js-promo_notification-popup-close');

			$closeButton.bind('click.close_promo_notification', function () {
				closeNotification();

				return false;
			});

			$document.bind('keydown.close_promo_notification', function (e) {
				if (e.which === 27) {
					closeNotification();
				}
			});

			$('body').append($notification);

			function closeNotification () {
				$notification.remove();

				$closeButton.unbind('click.close_promo_notification');
				$document.unbind('keydown.close_promo_notification');
			}
		}
	}

	return;
});

// Код для тестирования. Вставлять туда, где должны появиться инпуты.
/*<script type="text/javascript">
	(function () {
		if (localStorage && localStorage.notifications) {
			var notifications = JSON.parse(localStorage.notifications),
				map = {
					Title: 'title',
					Message: 'message',
					IconUrl: 'image'
				};

			if (notifications.MA) {
				for (var key in notifications.MA) {
					if (map[key]) {
						document.write('<input type="hidden" id="alarm_' + map[key] + '" value="' + notifications.MA[key] + '" />');
					}
				}
			}
		}
	})();
</script>*/;
