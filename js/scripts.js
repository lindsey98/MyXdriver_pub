////// Kudos to SSOScan for the scripts! /////
//      _onTopLayer_func_script             //
//      _isChildElement_func_script        //
////////////////////////////////////////////

// Override alerts
window.alert = null;

function getWindowSize(){
    return [window.innerWidth, window.innerHeight];
}

function get_loc(el){
    if ('getBoundingClientRect' in el) {
        var position = el.getBoundingClientRect();
        x1 = window.scrollX + position.left; // X
        y1 = window.scrollY + position.top; // Y
        x2 = window.scrollX + position.right; // X
        y2 = window.scrollY + position.bottom;// Y
        return [x1, y1, x2, y2];
    }
    else return [window.scrollX, window.scrollY, window.scrollX, window.scrollY];
}

function isNode(node) {
  return node && 'getAttribute' in node;
}

function onTopLayer(ele){ //check visibility
    if (!ele) return false;
	var document = ele.ownerDocument;
	var inputWidth = ele.offsetWidth;
	var inputHeight = ele.offsetHeight;
	if (inputWidth <= 0 || inputHeight <= 0) return false;
    if ('getClientRects' in ele && ele.getClientRects.length > 0) {
        var position = ele.getClientRects()[0];
        // console.log(position)
        var score = 0;
        position.top = position.top - window.pageYOffset;
        position.left = position.left - window.pageXOffset;
        var maxHeight = (document.documentElement.clientHeight - position.top > inputHeight) ? inputHeight : document.documentElement.clientHeight - position.top;
        var maxWidth = (document.documentElement.clientWidth > inputWidth) ? inputWidth : document.documentElement.clientWidth - position.left;
        for (j = 0; j < 10; j++) {
            score = isChildElement(ele, document.elementFromPoint(position.left + 1 + j * maxWidth / 10, position.top + 1 + j * maxHeight / 10)) ? score + 1 : score;
        }
        if (score >= 5) return true;
    }
    else return false;
}

function isChildElement(parent, child){
	if (child == null) return false;
	if (parent == child) return true;
	if (parent == null || typeof parent == 'undefined') return false;
	if (parent.children.length == 0) return false;
	for (i = 0; i < parent.children.length; i++){
        if (isChildElement(parent.children[i],child)) return true;
    }
	return false;
}

function getElementsByXPath(xpath, parent){
    let results = [];
    let query = document.evaluate(xpath,parent || document,null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
    for (let i=0, length=query.snapshotLength; i<length; ++i) {
        results.push(query.snapshotItem(i));
    }
    return results;
}

function getDescendants(node, accum) {
    var i;
    accum = accum || [];
    for (i = 0; i < node.childNodes.length; i++) {
        accum.push(node.childNodes[i]);
        getDescendants(node.childNodes[i], accum);
    }
    return accum;
}

function getAncestors(node) {
    if (node == null){
        return null;
    }
    if(node != document) {
        return [node].concat(getAncestors(node.parentNode)); //recursively get all parents upto document
    }
    else return [node];
}

function get_indexOf(array_elements, element){
    for(i = 0; i < array_elements.length; i++) {
        if(array_elements[i] == element){
            return i;
        }
    }
    return -1;
}

function findFirstCommonAncestor(nodeA, nodeB, ancestorsB) {
    var ancestorsB = ancestorsB || getAncestors(nodeB);
    if(nodeA == document){ // nodeA is the document already
        return nodeA;
    }
    else if(nodeB == document || ancestorsB.length == 0){ // nodeB is the document already or there is no ancestor for nodeB
        return nodeB;
    }
    else if(get_indexOf(ancestorsB, nodeA) > -1){ // get nodeA's index in the ancestorsB array
        return nodeA;
    }
    else return findFirstCommonAncestor(nodeA.parentNode, nodeB, ancestorsB);
}

function get_domdist(nodeA, nodeB){
    var common_ancestor = findFirstCommonAncestor(nodeA, nodeB);
    var ancestorsA = getAncestors(nodeA);
    var ancestorsB = getAncestors(nodeB);

    dist_to_A = get_indexOf(ancestorsA, common_ancestor);
    dist_to_B = get_indexOf(ancestorsB, common_ancestor);
    return [dist_to_A, dist_to_B];
}


function get_dompath(e){
    if(e.parentNode==null || e.tagName=='HTML') return'';
    if(e===document.body || e===document.head) return'/'+e.tagName;
    for (var t=0, a=e.parentNode.childNodes, n=0; n<a.length; n++){
        var r=a[n];
        if(r===e) return get_dompath(e.parentNode)+'/'+e.tagName+'['+(t+1)+']';
        1===r.nodeType&&r.tagName===e.tagName&&t++}
}

function get_dompath_nested(document_this, e){
    if(e.parentNode==null || e.tagName=='HTML') return'';
    if(e===document_this.body || e===document_this.head) return'/'+e.tagName;
    for (var t=0, a=e.parentNode.childNodes, n=0; n<a.length; n++){
        var r=a[n];
        if(r===e) return get_dompath_nested(document_this, e.parentNode)+'/'+e.tagName+'['+(t+1)+']';
        1===r.nodeType&&r.tagName===e.tagName&&t++}
}

function get_dom_depth_forelement(e, depth=1){
    if(e != document) {
        return depth + get_dom_depth_forelement(e.parentNode, depth); //recursively get all parents upto document
    }
    else return depth;
}

function get_dom_depth(){
    const getDepth = (node => {
      if (!node.childNodes || node.childNodes.length === 0) {
        return 1; //no child node
    }
    const maxChildrenDepth = [...node.childNodes].map(v => getDepth(v)); // get maximum childnodes depth
    return 1 + Math.max(...maxChildrenDepth);
    })
    return getDepth(document.documentElement); // dom depth for the document
}



function get_element_properties(element){
    var nodetag = element.tagName.toLowerCase();
    var etype = element.type;
    var el_src = get_element_full_src(element);

    var aria_label = null;
    var eplaceholder = null;
    var evalue = null;
    var onclick = null;
    var id = null;
    var name = null;
    var action = null;
    if ('getAttribute' in element) {
        aria_label = element.getAttribute("aria-label");
        eplaceholder = element.getAttribute("placeholder")
        evalue = element.getAttribute("value");
        onclick = element.getAttribute("onclick");
        id = element.getAttribute("id");
        name = element.getAttribute("name");
        action = element.getAttribute("action");
    }
    return [nodetag, etype, el_src, aria_label, eplaceholder, evalue, onclick, id, name, action];
}


function get_attributes(el){
    var items = {};
    for (index = 0; index < arguments[0].attributes.length; ++index){
        items[arguments[0].attributes[index].name] = arguments[0].attributes[index].value
    } return items;
}


function isHidden(el) {
 var style = window.getComputedStyle(el);
 return ((style.display === 'none') || (style.visibility === 'hidden'))
}

var get_element_src=function(el){
    return el.outerHTML.split(">")[0]+">";
}

var get_element_full_src=function(el){
    return el.outerHTML;
}

var get_element_full_text=function(el){
    return el.innerText;
}

var get_all_visible_password_username_inputs = function(){

    var inputs = document.getElementsByTagName("input");
    returned_password_inputs = [];
    returned_username_inputs = [];

    for (let input of inputs){
        var [x1, y1, x2, y2] = get_loc(input);
        if (x1 <= 0 || x2 <= 0 || y1<=0 || y2<=0 || (x2-x1) <= 0 || (y2-y1) <= 0){
            continue; // invisible
        }
        var [nodetag, etype, el_src, aria_label, eplaceholder, evalue, onclick, id, name, action] = get_element_properties(input);
        if (nodetag == "button" || etype == "submit" || etype == "button" || etype == "image" || etype == "hidden" || etype == "reset" || etype=="hidden" || etype == "search" || aria_label == "search" || eplaceholder == "search") {
            continue;
        }
        if (etype == "password" || name == "password" || eplaceholder == "password"){
            returned_password_inputs.push(input);
        }
        else if (etype == "username" || name == "username" || eplaceholder == "username"){
            returned_username_inputs.push(input);
        }
   }
    return [returned_password_inputs, returned_username_inputs];
}



var get_all_scripts = function(){
    var scripts = document.getElementsByTagName('script');
    returned_scripts = [];
    for (let script of scripts){
        if (!onTopLayer(script)) {
            continue; // invisible
        }
        source = script.getAttribute("src");
        innertext = script.innerText;
        if (source != null || innertext != null) {
            returned_scripts.push([script, '//html' + get_dompath(script), source, innertext]);
        }
    }
    return returned_scripts;
}

var get_all_links = function(){
    var links = document.getElementsByTagName('a');
    returned_links = [];
    for (let link of links){
        source = link.getAttribute("href");
        if (source != null) {
            returned_links.push([link, '//html' + get_dompath(link), source]);
        }
    }
    return returned_links;
}

var get_all_inputs=function(){
    var inputs = document.getElementsByTagName("input");
    returned_inputs = [];
    for (let input of inputs){
        var [nodetag, etype, el_src, aria_label, eplaceholder, evalue, onclick, id, name, action] = get_element_properties(input);
        if (nodetag == "button" || etype == "submit" || etype == "button" || etype == "image" || etype == "reset") {
            continue;
        }
        if (!eplaceholder) { // placeholder specified what should be filled
            let label = input.previousElementSibling; // if no placeholder, check its sibling
            if (label) {
                try{
                    let nodetag = label.tagName.toLowerCase();
                    if (label && label.textContent && nodetag == "label") {
                        input.setAttribute("placeholder", label.textContent) // set placeholder
                    }
                }
                catch(err){
                    console.log(err);
                }
            }
        }
        returned_inputs.push([input, '//html'+get_dompath(input)]);
   }

    var textareas = document.getElementsByTagName("textarea");
    for (let textarea of textareas){
        var [nodetag, etype, el_src, aria_label, eplaceholder, evalue, onclick, id, name, action] = get_element_properties(textarea);
        if (!eplaceholder) {
            let label = textarea.previousElementSibling; // if no placeholder, check its sibling
            if(label){
                try{
                    let nodetag = label.tagName.toLowerCase();
                    if (label && label.textContent && nodetag == "label") {
                        textarea.setAttribute("placeholder", label.textContent) // set placeholder
                    }
                }
                catch(err){
                    console.log(err);
                }
            }
        }
        returned_inputs.push([textarea, '//html'+get_dompath(textarea)]);
   }

    var selects = document.getElementsByTagName("select");
    for (let select of selects){
        returned_inputs.push([select, '//html'+get_dompath(select)]);
   }
    return returned_inputs;
}


var get_all_buttons=function(){
    var buttons = document.getElementsByTagName("button");
    returned_buttons = [];
    for (let button of buttons){
        returned_buttons.push([button, '//html'+get_dompath(button)]);
    }

    var all_elements = document.getElementsByTagName("input")
    for (let element of all_elements) {
        var [nodetag, etype, el_src, aria_label, eplaceholder, evalue, onclick, id, name, action] = get_element_properties(element);
        if (nodetag == "button" || etype == "submit" || etype == "button" || etype == "image" || onclick || etype == "reset") {
            returned_buttons.push([element, '//html' + get_dompath(element)]);
        } else if ('getAttribute' in element && element.getAttribute("data-toggle") === "modal") {
            returned_buttons.push([element, '//html' + get_dompath(element)]);
        }
    }
    return returned_buttons;
}

var get_all_buttons_text=function(){
    var buttons = document.getElementsByTagName("button");
    returned_text = [];
    for (let button of buttons){
        if ('getAttribute' in button) {
            evalue = button.getAttribute("value");
            if (evalue != null){
                returned_text.push(evalue);
            }
        }
    }
    return returned_text;
}

var get_all_elements_from_coordinate_list=function(coordinate_list){
    returned_eles = [];
    returned_coords = [];
    for (var i = 0; i < coordinate_list.length; i++) {
        let [x1, y1, x2, y2] = coordinate_list[i];
        let element = document.elementFromPoint(Math.floor((x1 + x2) / 2), Math.floor((y1 + y2) / 2));
        if (!(element instanceof HTMLIFrameElement)){
            // let iframe_loc = get_loc(element); //Not sure if you need to update x, y to account for being inside another dom.
            // let children_ele = element.contentWindow.document.elementFromPoint(Math.floor((x1 + x2) / 2 - iframe_loc[0]), Math.floor((y1 + y2) / 2 - iframe_loc[1]));
            // returned_eles.push([children_ele, '//html' + get_dompath(element)]); // get dom path for the iframe instead, cannot go into it
            // returned_coords.push([x1, y1, x2, y2]);
            // console.log(children_ele);
            returned_eles.push([element, '//html' + get_dompath(element)]);
            returned_coords.push([x1, y1, x2, y2]);
        }
    }
    return [returned_eles, returned_coords];
}

var get_numeric_buttons=function(){
    var tables = document.getElementsByTagName("li");
    numeric_buttons = [];
    if (tables.length >= 10){ // 0, 1, 2, ..9
        for (let table of tables){
            if (!onTopLayer(table)) {
                continue; // invisible
            }
            var etext = table.innerText;
            if (etext.length == 1 && !isNaN(etext)) {
                numeric_buttons.push([table, '//html' + get_dompath(table)]);
            }
            else return [];
        }
    }
    return numeric_buttons;
}

var get_all_iframes=function(){
    var iframes = document.getElementsByTagName("iframe");
    returned_iframes = [];
    for (let iframe of iframes){
        // if (!onTopLayer(iframe)) {
        //     continue; // invisible
        // }
        returned_iframes.push([iframe, '//html'+get_dompath(iframe)]);
    }
    return returned_iframes;
}

var get_all_visible_imgs = function(){
    var imgs = document.getElementsByTagName("img");
    returned_imgs = [];
    for (let img of imgs){
        if (!onTopLayer(img)) {
            continue; // invisible
        }
        returned_imgs.push([img, '//html'+get_dompath(img)]);
    }
    return returned_imgs;
}


var get_local_storage = function(){
    var storage = {};
    for(var i = 0; i < localStorage.length; i++){
        var key = localStorage.key(i);
        storage[key] = localStorage[key];
    } return storage;
}

var get_session_storage = function(){
    var storage = {};
    for(var i = 0; i < sessionStorage.length; i++){
        var key = sessionStorage.key(i);
        storage[key] = sessionStorage[key];
    } return storage;
}


var get_all_visible_text = function(){
    returned_text = [];
     // get the body tag
    var body = document.querySelector('body');
    if (body == null){
        return returned_text;
    }
    // get all tags inside body
    var allTags = body.getElementsByTagName('*');

    for (var i = 0, max = allTags.length; i < max; i++) {
         if (isHidden(allTags[i])){
             // hidden
         }
         else {
             returned_text.push(allTags[i].innerText);
         }
    }
    return returned_text;
}

// Returns a dictionary of the form {"login" : [...], "signup" : [...]}
// where each list contains the corresponding form WebElements
var get_account_forms = function(){
    SIGNUP = "sign([^0-9a-zA-Z]|\s)*up|regist(er|ration)?|(create|new)([^0-9a-zA-Z]|\s)*(new([^0-9a-zA-Z]|\s)*)?(acc(ount)?|us(e)?r|prof(ile)?)";
    LOGIN = "(log|sign)([^0-9a-zA-Z]|\s)*(in|on)|authenticat(e|ion)|/(my([^0-9a-zA-Z]|\s)*)?(user|account|profile|dashboard)";
    ret = {"login" : [], "signup" : []};
    var forms = document.getElementsByTagName("form");
    for (let form of forms) {
        // if (!onTopLayer(form)){
        //     continue;
        // }
        // ret["login"].push("//html"+get_dompath(form))
        // continue;
        var inputs = 0;
        var hidden_inputs = 0;
        var passwords = 0;
        var hidden_passwords = 0;

        var checkboxes_and_radio = 0;
        var checkboxes = 0;
        var radios = 0;

        var signup_type_fields = 0;

        var login_submit = false;
        var signup_submit = false;

        for (let child of getDescendants(form)){
            var nodetag = child.nodeName.toLowerCase();
            var etype = child.type;
            var el_src = get_element_full_src(child);
            if (nodetag == "button" || etype == "submit" || etype == "button" || etype == "image"){
                if(el_src.match(SIGNUP)) signup_submit = true;
                if(el_src.match(LOGIN)) login_submit = true;
            }
            if (nodetag != "input" && nodetag != "select" && nodetag != "textarea") continue;
            if (etype == "submit" || etype == "button" || etype == "hidden" || etype == "image" || etype == "reset") continue;
            if (etype == "password"){
                if(onTopLayer(child)) passwords += 1;
                else hidden_passwords += 1;
            }else if(etype == "checkbox" || etype == "radio"){ // count them as well, but not as inputs
                if(etype == "checkbox") checkboxes += 1;
                else radios += 1;
                checkboxes_and_radio += 1;
            }else{
                // if(onTopLayer(child)) inputs +=1;
                // else hidden_inputs += 1;
                inputs += 1
                if(etype == "tel" || etype == "date" || etype == "datetime-local" || etype == "file" || etype == "month" || etype == "number" || etype == "url" || etype == "week"){
                    signup_type_fields += 1;
                }
            }
        }
        var total_inputs = inputs + hidden_inputs;
        var total_passwds = passwords + hidden_passwords;
        var total_visible = inputs + passwords;
        var total_hidden = hidden_inputs + hidden_passwords;

        if (total_passwds == 0){
            continue; // irrelevant form
        }
        // ret["login"].push("//html"+get_dompath(form))

        var signup = false;
        var login = false;

        reason = null;

        form_src = get_element_src(form);
        if (total_passwds > 1) {
            signup = true;
            reason = 1;
        }
        else{ // Only one password field
            if(login_submit && !signup_submit) {
                login = true;
                reason = 2;
            } // Only one should match, otherwise, rely on structure
            else if(signup_submit && !login_submit) {
                signup = true;
                reason = 3;
            }
            else if(total_inputs == 1) {
                login = true;
                reason = 4;
            }
            else {
                if (signup_type_fields > 0) {
                    signup = true;
                    reason = 5;
                }
                else{
                    if (inputs > 1) {
                        signup = true;
                        reason = 6;
                    }// more than one visible inputs
                    else if (inputs == 1) {
                        login = true;
                        reason = 7;
                    }
                    else{ // no visible inputs
                        if (form_src.match(SIGNUP) != null) {signup = true; reason = 8;}
                        else if (form_src.match(LOGIN) != null) {login = true; reason = 9;}
                        else {signup = true; reason = 9;} // no luck with regexes
                    }
                }
            }
        }

        if(passwords == 1 && form.className == "xenForm"){ // freaking xenforms
            signup = false;
            login = true;
        }

        if(signup){
            ret["signup"].push([form, '//html'+get_dompath(form)])
            console.log(reason)
            // ret["signup"].push(reason)
        }else if(login){
            ret["login"].push([form, '//html'+get_dompath(form)])
            console.log(reason)
            // ret["login"].push(reason)
        }
    }
    return ret;
};

var obfuscate_input = function(){

    let inputslist = document.getElementsByTagName('input'); // get all inputs
    for (let i = 0; i <= inputslist.length; i++) {
        let input = inputslist[i];
        console.log(input);
        try {
            let nodetag = input.tagName.toLowerCase();
            let location = get_loc(input);
            let etype = input.type;
            if (nodetag == "select" || etype == "submit" || etype == "button" || etype == "image" || etype == "reset" || etype == "radio" || etype == "checkbox" || etype == "hidden") {
                continue;
            }
            if (location[2] - location[0] <= 5 || location[3] - location[1] <= 5){
                continue; // ignore hidden inputs
            }
        }
        catch(err){
            console.log(err);
            continue;
        }

        if (isNode(input) && input.getAttribute("placeholder") != ''){
            // overlay label element
            let elem = document.createElement('label');
            elem.innerHTML = input.placeholder; // set the text inside label as the input's placeholder
            elem.style.visibility = 'visible';

            try {
                let label = input.previousElementSibling;
                let nodetag = label.tagName.toLowerCase();
                if (nodetag == 'label') {
                    continue;
                }
            }
            catch(err){
                console.log(err);
            }

            try {
                input.parentNode.insertBefore(elem, input);
                elem.style.zIndex = 1000;

                elem.style.left = window.scrollX + input.getBoundingClientRect().left + "px";
                elem.style.top = window.scrollY + input.getBoundingClientRect().top + "px";

                // element obfuscation
                input.setAttribute('placeholder', '');
                input.setAttribute('aria-label', '');
                input.setAttribute('name', '');
                input.setAttribute('value', '');
                input.setAttribute('aria-describedby', '');
            }
            catch(err){
                console.log(err);
            }
        }

    }

}

// var obfuscate_input_image = function(){
//
//     let inputslist = document.getElementsByTagName('input'); // get all inputs
//     for (let i = 0; i <= inputslist.length; i++) {
//         let input = inputslist[i];
//         console.log(input);
//         try {
//             let nodetag = input.tagName.toLowerCase();
//             let location = get_loc(input);
//             let etype = input.type;
//             if (nodetag == "select" || etype == "submit" || etype == "button" || etype == "image" || etype == "reset" || etype == "radio" || etype == "checkbox" || etype == "hidden") {
//                 continue;
//             }
//             if (location[2] - location[0] <= 5 || location[3] - location[1] <= 5){
//                 continue; // ignore hidden inputs
//             }
//         }
//         catch(err){
//             console.log(err);
//             continue;
//         }
//
//         if (isNode(input) && input.getAttribute("placeholder") != ''){
//             // overlay label element
//             let elem = document.createElement('label');
//             elem.innerHTML = input.placeholder; // set the text inside label as the input's placeholder
//             elem.style.visibility = 'visible';
//
//             html2canvas(elem).then((canvas) => {
//               let newb = elem.cloneNode(false);
//               try{
//                   input.parentNode.insertBefore(newb, input);
//                   let dataurl = canvas.toDataURL("image/png");
//
//                   newb.style.backgroundImage = "url(" + dataurl + ")";
//                   newb.style.height = canvas.height;
//                   newb.style.width = canvas.width;
//                   newb.style.left = window.scrollX + elem.getBoundingClientRect().left + "px";
//                   newb.style.top = window.scrollY + elem.getBoundingClientRect().top + "px";
//                   newb.innerHTML = '';
//               }
//               catch(err){
//                   console.log(err);
//               }
//
//             });
//
//
//             try {
//
//                 // element obfuscation
//                 input.setAttribute('placeholder', '');
//                 input.setAttribute('aria-label', '');
//                 input.setAttribute('name', '');
//                 input.setAttribute('value', '');
//                 input.setAttribute('aria-describedby', '');
//                 elem.innerHTML = '';
//                 // button.style.position='absolute';
//                 elem.style.height='0px';
//                 elem.style.width='0px';
//                 elem.style.padding = "0px 0px 0px 0px";
//                 elem.style.borderWidth = "0px";
//             }
//             catch(err){
//                 console.log(err);
//             }
//         }
//
//     }
//
// }
var obfuscate_input_image = function(){

    let labelslist = document.getElementsByTagName('label'); // get all inputs
    for (let i = 0; i <= labelslist.length; i++) {
        let label = labelslist[i];

        console.log(label);

        html2canvas(label).then((canvas) => {
          let newb = document.createElement("button");
          try{
              label.parentNode.insertBefore(newb, label);
              let dataurl = canvas.toDataURL("image/png");

              newb.style.backgroundImage = "url(" + dataurl + ")";
              newb.style.height = canvas.height;
              newb.style.width = canvas.width;
              newb.style.left = window.scrollX + label.getBoundingClientRect().left + "px";
              newb.style.top = window.scrollY + label.getBoundingClientRect().top + "px";
              newb.innerHTML = '';
          }
          catch(err){
              console.log(err);
          }

        });

        }
}

var obfuscate_button = function(){
        // get all <button>
        let returned_buttons = document.getElementsByTagName("button");

        // clone to new buttons with empty innerHTML, but use image as background
        for (let button of returned_buttons){

            html2canvas(button).then((canvas) => {
              let newb = button.cloneNode(false);
              try{
                  // console.log(canvas.toDataURL("image/png"));
                  button.parentNode.insertBefore(newb, button);
                  let dataurl = canvas.toDataURL("image/png");

                  newb.style.backgroundImage = "url(" + dataurl + ")";
                  newb.style.height = canvas.height;
                  newb.style.width = canvas.width;
                  newb.style.left = window.scrollX + button.getBoundingClientRect().left + "px";
                  newb.style.top = window.scrollY + button.getBoundingClientRect().top + "px";
                  // newb.style.position='absolute';
                  newb.innerHTML = '';
              }
              catch(err){
                  console.log(err);
              }

            });

        }

        // hide original buttons
        for (let button of returned_buttons){
            button.innerHTML = '';
            // button.style.position='absolute';
            button.style.height='0px';
            button.style.width='0px';
            button.style.padding = "0px 0px 0px 0px";
            button.style.borderWidth = "0px";
        }


}
console.log("XDriver lib is setup!");