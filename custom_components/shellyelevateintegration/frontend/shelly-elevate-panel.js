var e=globalThis,t=e.ShadowRoot&&(e.ShadyCSS===void 0||e.ShadyCSS.nativeShadow)&&`adoptedStyleSheets`in Document.prototype&&`replace`in CSSStyleSheet.prototype,n=Symbol(),r=new WeakMap,i=class{constructor(e,t,r){if(this._$cssResult$=!0,r!==n)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,n=this.t;if(t&&e===void 0){let t=n!==void 0&&n.length===1;t&&(e=r.get(n)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),t&&r.set(n,e))}return e}toString(){return this.cssText}},a=e=>new i(typeof e==`string`?e:e+``,void 0,n),o=(e,...t)=>new i(e.length===1?e[0]:t.reduce((t,n,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if(typeof e==`number`)return e;throw Error(`Value passed to 'css' function must be a 'css' function result: `+e+`. Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.`)})(n)+e[r+1],e[0]),e,n),s=(n,r)=>{if(t)n.adoptedStyleSheets=r.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let t of r){let r=document.createElement(`style`),i=e.litNonce;i!==void 0&&r.setAttribute(`nonce`,i),r.textContent=t.cssText,n.appendChild(r)}},c=t?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t=``;for(let n of e.cssRules)t+=n.cssText;return a(t)})(e):e,{is:l,defineProperty:u,getOwnPropertyDescriptor:ee,getOwnPropertyNames:te,getOwnPropertySymbols:ne,getPrototypeOf:re}=Object,ie=globalThis,ae=ie.trustedTypes,oe=ae?ae.emptyScript:``,se=ie.reactiveElementPolyfillSupport,d=(e,t)=>e,ce={toAttribute(e,t){switch(t){case Boolean:e=e?oe:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},le=(e,t)=>!l(e,t),ue={attribute:!0,type:String,converter:ce,reflect:!1,useDefault:!1,hasChanged:le};Symbol.metadata??=Symbol(`metadata`),ie.litPropertyMetadata??=new WeakMap;var f=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=ue){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),r=this.getPropertyDescriptor(e,n,t);r!==void 0&&u(this.prototype,e,r)}}static getPropertyDescriptor(e,t,n){let{get:r,set:i}=ee(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){let a=r?.call(this);i?.call(this,t),this.requestUpdate(e,a,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??ue}static _$Ei(){if(this.hasOwnProperty(d(`elementProperties`)))return;let e=re(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(d(`finalized`)))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(d(`properties`))){let e=this.properties,t=[...te(e),...ne(e)];for(let n of t)this.createProperty(n,e[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[e,n]of t)this.elementProperties.set(e,n)}this._$Eh=new Map;for(let[e,t]of this.elementProperties){let n=this._$Eu(e,t);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let e of n)t.unshift(c(e))}else e!==void 0&&t.push(c(e));return t}static _$Eu(e,t){let n=t.attribute;return!1===n?void 0:typeof n==`string`?n:typeof e==`string`?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return s(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,n);if(r!==void 0&&!0===n.reflect){let i=(n.converter?.toAttribute===void 0?ce:n.converter).toAttribute(t,n.type);this._$Em=e,i==null?this.removeAttribute(r):this.setAttribute(r,i),this._$Em=null}}_$AK(e,t){let n=this.constructor,r=n._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let e=n.getPropertyOptions(r),i=typeof e.converter==`function`?{fromAttribute:e.converter}:e.converter?.fromAttribute===void 0?ce:e.converter;this._$Em=r;let a=i.fromAttribute(t,e.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(e,t,n,r=!1,i){if(e!==void 0){let a=this.constructor;if(!1===r&&(i=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??le)(i,t)||n.useDefault&&n.reflect&&i===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,t,n)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:r,wrapped:i},a){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??t??this[e]),!0!==i||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}let e=this.constructor.elementProperties;if(e.size>0)for(let[t,n]of e){let{wrapped:e}=n,r=this[t];!0!==e||this._$AL.has(t)||r===void 0||this.C(t,void 0,n,r)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};f.elementStyles=[],f.shadowRootOptions={mode:`open`},f[d(`elementProperties`)]=new Map,f[d(`finalized`)]=new Map,se?.({ReactiveElement:f}),(ie.reactiveElementVersions??=[]).push(`2.1.2`);var de=globalThis,fe=e=>e,pe=de.trustedTypes,me=pe?pe.createPolicy(`lit-html`,{createHTML:e=>e}):void 0,he=`$lit$`,p=`lit$${Math.random().toFixed(9).slice(2)}$`,ge=`?`+p,_e=`<${ge}>`,m=document,h=()=>m.createComment(``),g=e=>e===null||typeof e!=`object`&&typeof e!=`function`,ve=Array.isArray,ye=e=>ve(e)||typeof e?.[Symbol.iterator]==`function`,be=`[ 	
\f\r]`,xe=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Se=/-->/g,Ce=/>/g,_=RegExp(`>|${be}(?:([^\\s"'>=/]+)(${be}*=${be}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,`g`),we=/'/g,Te=/"/g,Ee=/^(?:script|style|textarea|title)$/i,v=(e=>(t,...n)=>({_$litType$:e,strings:t,values:n}))(1),y=Symbol.for(`lit-noChange`),b=Symbol.for(`lit-nothing`),De=new WeakMap,x=m.createTreeWalker(m,129);function Oe(e,t){if(!ve(e)||!e.hasOwnProperty(`raw`))throw Error(`invalid template strings array`);return me===void 0?t:me.createHTML(t)}var ke=(e,t)=>{let n=e.length-1,r=[],i,a=t===2?`<svg>`:t===3?`<math>`:``,o=xe;for(let t=0;t<n;t++){let n=e[t],s,c,l=-1,u=0;for(;u<n.length&&(o.lastIndex=u,c=o.exec(n),c!==null);)u=o.lastIndex,o===xe?c[1]===`!--`?o=Se:c[1]===void 0?c[2]===void 0?c[3]!==void 0&&(o=_):(Ee.test(c[2])&&(i=RegExp(`</`+c[2],`g`)),o=_):o=Ce:o===_?c[0]===`>`?(o=i??xe,l=-1):c[1]===void 0?l=-2:(l=o.lastIndex-c[2].length,s=c[1],o=c[3]===void 0?_:c[3]===`"`?Te:we):o===Te||o===we?o=_:o===Se||o===Ce?o=xe:(o=_,i=void 0);let ee=o===_&&e[t+1].startsWith(`/>`)?` `:``;a+=o===xe?n+_e:l>=0?(r.push(s),n.slice(0,l)+he+n.slice(l)+p+ee):n+p+(l===-2?t:ee)}return[Oe(e,a+(e[n]||`<?>`)+(t===2?`</svg>`:t===3?`</math>`:``)),r]},Ae=class e{constructor({strings:t,_$litType$:n},r){let i;this.parts=[];let a=0,o=0,s=t.length-1,c=this.parts,[l,u]=ke(t,n);if(this.el=e.createElement(l,r),x.currentNode=this.el.content,n===2||n===3){let e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;(i=x.nextNode())!==null&&c.length<s;){if(i.nodeType===1){if(i.hasAttributes())for(let e of i.getAttributeNames())if(e.endsWith(he)){let t=u[o++],n=i.getAttribute(e).split(p),r=/([.?@])?(.*)/.exec(t);c.push({type:1,index:a,name:r[2],strings:n,ctor:r[1]===`.`?Ne:r[1]===`?`?Pe:r[1]===`@`?Fe:C}),i.removeAttribute(e)}else e.startsWith(p)&&(c.push({type:6,index:a}),i.removeAttribute(e));if(Ee.test(i.tagName)){let e=i.textContent.split(p),t=e.length-1;if(t>0){i.textContent=pe?pe.emptyScript:``;for(let n=0;n<t;n++)i.append(e[n],h()),x.nextNode(),c.push({type:2,index:++a});i.append(e[t],h())}}}else if(i.nodeType===8){if(i.data===ge)c.push({type:2,index:a});else{let e=-1;for(;(e=i.data.indexOf(p,e+1))!==-1;)c.push({type:7,index:a}),e+=p.length-1}}a++}}static createElement(e,t){let n=m.createElement(`template`);return n.innerHTML=e,n}};function S(e,t,n=e,r){if(t===y)return t;let i=r===void 0?n._$Cl:n._$Co?.[r],a=g(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(e),i._$AT(e,n,r)),r===void 0?n._$Cl=i:(n._$Co??=[])[r]=i),i!==void 0&&(t=S(e,i._$AS(e,t.values),i,r)),t}var je=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,r=(e?.creationScope??m).importNode(t,!0);x.currentNode=r;let i=x.nextNode(),a=0,o=0,s=n[0];for(;s!==void 0;){if(a===s.index){let t;s.type===2?t=new Me(i,i.nextSibling,this,e):s.type===1?t=new s.ctor(i,s.name,s.strings,this,e):s.type===6&&(t=new Ie(i,this,e)),this._$AV.push(t),s=n[++o]}a!==s?.index&&(i=x.nextNode(),a++)}return x.currentNode=m,r}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings===void 0?n._$AI(e[t]):(n._$AI(e,n,t),t+=n.strings.length-2)),t++}},Me=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,r){this.type=2,this._$AH=b,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=S(this,e,t),g(e)?e===b||e==null||e===``?(this._$AH!==b&&this._$AR(),this._$AH=b):e!==this._$AH&&e!==y&&this._(e):e._$litType$===void 0?e.nodeType===void 0?ye(e)?this.k(e):this._(e):this.T(e):this.$(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==b&&g(this._$AH)?this._$AA.nextSibling.data=e:this.T(m.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,r=typeof n==`number`?this._$AC(e):(n.el===void 0&&(n.el=Ae.createElement(Oe(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===r)this._$AH.p(t);else{let e=new je(r,this),n=e.u(this.options);e.p(t),this.T(n),this._$AH=e}}_$AC(e){let t=De.get(e.strings);return t===void 0&&De.set(e.strings,t=new Ae(e)),t}k(t){ve(this._$AH)||(this._$AH=[],this._$AR());let n=this._$AH,r,i=0;for(let a of t)i===n.length?n.push(r=new e(this.O(h()),this.O(h()),this,this.options)):r=n[i],r._$AI(a),i++;i<n.length&&(this._$AR(r&&r._$AB.nextSibling,i),n.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let t=fe(e).nextSibling;fe(e).remove(),e=t}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},C=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,r,i){this.type=1,this._$AH=b,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=i,n.length>2||n[0]!==``||n[1]!==``?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=b}_$AI(e,t=this,n,r){let i=this.strings,a=!1;if(i===void 0)e=S(this,e,t,0),a=!g(e)||e!==this._$AH&&e!==y,a&&(this._$AH=e);else{let r=e,o,s;for(e=i[0],o=0;o<i.length-1;o++)s=S(this,r[n+o],t,o),s===y&&(s=this._$AH[o]),a||=!g(s)||s!==this._$AH[o],s===b?e=b:e!==b&&(e+=(s??``)+i[o+1]),this._$AH[o]=s}a&&!r&&this.j(e)}j(e){e===b?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??``)}},Ne=class extends C{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===b?void 0:e}},Pe=class extends C{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==b)}},Fe=class extends C{constructor(e,t,n,r,i){super(e,t,n,r,i),this.type=5}_$AI(e,t=this){if((e=S(this,e,t,0)??b)===y)return;let n=this._$AH,r=e===b&&n!==b||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,i=e!==b&&(n===b||r);r&&this.element.removeEventListener(this.name,this,n),i&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH==`function`?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},Ie=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){S(this,e)}},Le={M:he,P:p,A:ge,C:1,L:ke,R:je,D:ye,V:S,I:Me,H:C,N:Pe,U:Fe,B:Ne,F:Ie},Re=de.litHtmlPolyfillSupport;Re?.(Ae,Me),(de.litHtmlVersions??=[]).push(`3.3.3`);var ze=(e,t,n)=>{let r=n?.renderBefore??t,i=r._$litPart$;if(i===void 0){let e=n?.renderBefore??null;r._$litPart$=i=new Me(t.insertBefore(h(),e),e,void 0,n??{})}return i._$AI(e),i},Be=globalThis,w=class extends f{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=ze(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return y}};w._$litElement$=!0,w.finalized=!0,Be.litElementHydrateSupport?.({LitElement:w});var Ve=Be.litElementPolyfillSupport;Ve?.({LitElement:w}),(Be.litElementVersions??=[]).push(`4.2.2`);var He=`M13 14H11V9H13M13 18H11V16H13M1 21H23L12 2L1 21Z`,Ue=`M13,13H11V7H13M13,17H11V15H13M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2Z`,We=`M21.7 18.6V17.6L22.8 16.8C22.9 16.7 23 16.6 22.9 16.5L21.9 14.8C21.9 14.7 21.7 14.7 21.6 14.7L20.4 15.2C20.1 15 19.8 14.8 19.5 14.7L19.3 13.4C19.3 13.3 19.2 13.2 19.1 13.2H17.1C16.9 13.2 16.8 13.3 16.8 13.4L16.6 14.7C16.3 14.9 16.1 15 15.8 15.2L14.6 14.7C14.5 14.7 14.4 14.7 14.3 14.8L13.3 16.5C13.3 16.6 13.3 16.7 13.4 16.8L14.5 17.6V18.6L13.4 19.4C13.3 19.5 13.2 19.6 13.3 19.7L14.3 21.4C14.4 21.5 14.5 21.5 14.6 21.5L15.8 21C16 21.2 16.3 21.4 16.6 21.5L16.8 22.8C16.9 22.9 17 23 17.1 23H19.1C19.2 23 19.3 22.9 19.3 22.8L19.5 21.5C19.8 21.3 20 21.2 20.3 21L21.5 21.4C21.6 21.4 21.7 21.4 21.8 21.3L22.8 19.6C22.9 19.5 22.9 19.4 22.8 19.4L21.7 18.6M18 19.5C17.2 19.5 16.5 18.8 16.5 18S17.2 16.5 18 16.5 19.5 17.2 19.5 18 18.8 19.5 18 19.5M12.3 22H3C1.9 22 1 21.1 1 20V4C1 2.9 1.9 2 3 2H21C22.1 2 23 2.9 23 4V13.1C22.4 12.5 21.7 12 21 11.7V6H3V20H11.3C11.5 20.7 11.8 21.4 12.3 22Z`,Ge=`M12,3A9,9 0 0,0 3,12H0L4,16L8,12H5A7,7 0 0,1 12,5A7,7 0 0,1 19,12A7,7 0 0,1 12,19C10.5,19 9.09,18.5 7.94,17.7L6.5,19.14C8.04,20.3 9.94,21 12,21A9,9 0 0,0 21,12A9,9 0 0,0 12,3M14,12A2,2 0 0,0 12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12Z`,Ke=`M18,11V12.5C21.19,12.5 23.09,16.05 21.33,18.71L20.24,17.62C21.06,15.96 19.85,14 18,14V15.5L15.75,13.25L18,11M18,22V20.5C14.81,20.5 12.91,16.95 14.67,14.29L15.76,15.38C14.94,17.04 16.15,19 18,19V17.5L20.25,19.75L18,22M19,3H18V1H16V3H8V1H6V3H5A2,2 0 0,0 3,5V19A2,2 0 0,0 5,21H14C13.36,20.45 12.86,19.77 12.5,19H5V8H19V10.59C19.71,10.7 20.39,10.94 21,11.31V5A2,2 0 0,0 19,3Z`,qe=`M12 2C6.5 2 2 6.5 2 12S6.5 22 12 22 22 17.5 22 12 17.5 2 12 2M10 17L5 12L6.41 10.59L10 14.17L17.59 6.58L19 8L10 17Z`,Je=`M7.41,8.58L12,13.17L16.59,8.58L18,10L12,16L6,10L7.41,8.58Z`,Ye=`M12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2Z`,Xe=`M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z`,Ze=`M12,8A4,4 0 0,1 16,12A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8M12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12A2,2 0 0,0 12,10M10,22C9.75,22 9.54,21.82 9.5,21.58L9.13,18.93C8.5,18.68 7.96,18.34 7.44,17.94L4.95,18.95C4.73,19.03 4.46,18.95 4.34,18.73L2.34,15.27C2.21,15.05 2.27,14.78 2.46,14.63L4.57,12.97L4.5,12L4.57,11L2.46,9.37C2.27,9.22 2.21,8.95 2.34,8.73L4.34,5.27C4.46,5.05 4.73,4.96 4.95,5.05L7.44,6.05C7.96,5.66 8.5,5.32 9.13,5.07L9.5,2.42C9.54,2.18 9.75,2 10,2H14C14.25,2 14.46,2.18 14.5,2.42L14.87,5.07C15.5,5.32 16.04,5.66 16.56,6.05L19.05,5.05C19.27,4.96 19.54,5.05 19.66,5.27L21.66,8.73C21.79,8.95 21.73,9.22 21.54,9.37L19.43,11L19.5,12L19.43,13L21.54,14.63C21.73,14.78 21.79,15.05 21.66,15.27L19.66,18.73C19.54,18.95 19.27,19.04 19.05,18.95L16.56,17.95C16.04,18.34 15.5,18.68 14.87,18.93L14.5,21.58C14.46,21.82 14.25,22 14,22H10M11.25,4L10.88,6.61C9.68,6.86 8.62,7.5 7.85,8.39L5.44,7.35L4.69,8.65L6.8,10.2C6.4,11.37 6.4,12.64 6.8,13.8L4.68,15.36L5.43,16.66L7.86,15.62C8.63,16.5 9.68,17.14 10.87,17.38L11.24,20H12.76L13.13,17.39C14.32,17.14 15.37,16.5 16.14,15.62L18.57,16.66L19.32,15.36L17.2,13.81C17.6,12.64 17.6,11.37 17.2,10.2L19.31,8.65L18.56,7.35L16.15,8.39C15.38,7.5 14.32,6.86 13.12,6.62L12.75,4H11.25Z`,Qe=`M15.9,18.45C17.25,18.45 18.35,17.35 18.35,16C18.35,14.65 17.25,13.55 15.9,13.55C14.54,13.55 13.45,14.65 13.45,16C13.45,17.35 14.54,18.45 15.9,18.45M21.1,16.68L22.58,17.84C22.71,17.95 22.75,18.13 22.66,18.29L21.26,20.71C21.17,20.86 21,20.92 20.83,20.86L19.09,20.16C18.73,20.44 18.33,20.67 17.91,20.85L17.64,22.7C17.62,22.87 17.47,23 17.3,23H14.5C14.32,23 14.18,22.87 14.15,22.7L13.89,20.85C13.46,20.67 13.07,20.44 12.71,20.16L10.96,20.86C10.81,20.92 10.62,20.86 10.54,20.71L9.14,18.29C9.05,18.13 9.09,17.95 9.22,17.84L10.7,16.68L10.65,16L10.7,15.31L9.22,14.16C9.09,14.05 9.05,13.86 9.14,13.71L10.54,11.29C10.62,11.13 10.81,11.07 10.96,11.13L12.71,11.84C13.07,11.56 13.46,11.32 13.89,11.15L14.15,9.29C14.18,9.13 14.32,9 14.5,9H17.3C17.47,9 17.62,9.13 17.64,9.29L17.91,11.15C18.33,11.32 18.73,11.56 19.09,11.84L20.83,11.13C21,11.07 21.17,11.13 21.26,11.29L22.66,13.71C22.75,13.86 22.71,14.05 22.58,14.16L21.1,15.31L21.15,16L21.1,16.68M6.69,8.07C7.56,8.07 8.26,7.37 8.26,6.5C8.26,5.63 7.56,4.92 6.69,4.92A1.58,1.58 0 0,0 5.11,6.5C5.11,7.37 5.82,8.07 6.69,8.07M10.03,6.94L11,7.68C11.07,7.75 11.09,7.87 11.03,7.97L10.13,9.53C10.08,9.63 9.96,9.67 9.86,9.63L8.74,9.18L8,9.62L7.81,10.81C7.79,10.92 7.7,11 7.59,11H5.79C5.67,11 5.58,10.92 5.56,10.81L5.4,9.62L4.64,9.18L3.5,9.63C3.41,9.67 3.3,9.63 3.24,9.53L2.34,7.97C2.28,7.87 2.31,7.75 2.39,7.68L3.34,6.94L3.31,6.5L3.34,6.06L2.39,5.32C2.31,5.25 2.28,5.13 2.34,5.03L3.24,3.47C3.3,3.37 3.41,3.33 3.5,3.37L4.63,3.82L5.4,3.38L5.56,2.19C5.58,2.08 5.67,2 5.79,2H7.59C7.7,2 7.79,2.08 7.81,2.19L8,3.38L8.74,3.82L9.86,3.37C9.96,3.33 10.08,3.37 10.13,3.47L11.03,5.03C11.09,5.13 11.07,5.25 11,5.32L10.03,6.06L10.06,6.5L10.03,6.94Z`,$e=`M19,21H8V7H19M19,5H8A2,2 0 0,0 6,7V21A2,2 0 0,0 8,23H19A2,2 0 0,0 21,21V7A2,2 0 0,0 19,5M16,1H4A2,2 0 0,0 2,3V17H4V3H16V1Z`,et=`M15,9H5V5H15M12,19A3,3 0 0,1 9,16A3,3 0 0,1 12,13A3,3 0 0,1 15,16A3,3 0 0,1 12,19M17,3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V7L17,3Z`,tt=`M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z`,T=`M12,16A2,2 0 0,1 14,18A2,2 0 0,1 12,20A2,2 0 0,1 10,18A2,2 0 0,1 12,16M12,10A2,2 0 0,1 14,12A2,2 0 0,1 12,14A2,2 0 0,1 10,12A2,2 0 0,1 12,10M12,4A2,2 0 0,1 14,6A2,2 0 0,1 12,8A2,2 0 0,1 10,6A2,2 0 0,1 12,4Z`,E=`M5,20H19V18H5M19,9H15V3H9V9H5L12,16L19,9Z`,nt=`M8 17V15H16V17H8M16 10L12 14L8 10H10.5V6H13.5V10H16M12 2C17.5 2 22 6.5 22 12C22 17.5 17.5 22 12 22C6.5 22 2 17.5 2 12C2 6.5 6.5 2 12 2M12 4C7.58 4 4 7.58 4 12C4 16.42 7.58 20 12 20C16.42 20 20 16.42 20 12C20 7.58 16.42 4 12 4Z`,rt=`M10,18H6V16H10V18M10,14H6V12H10V14M10,1V2H6C4.89,2 4,2.89 4,4V20A2,2 0 0,0 6,22H10V23H12V1H10M20,8V20C20,21.11 19.11,22 18,22H14V20H18V11H14V9H18.5L14,4.5V2L20,8M16,14H14V12H16V14M16,18H14V16H16V18Z`,it=`M10,9A1,1 0 0,1 11,8A1,1 0 0,1 12,9V13.47L13.21,13.6L18.15,15.79C18.68,16.03 19,16.56 19,17.14V21.5C18.97,22.32 18.32,22.97 17.5,23H11C10.62,23 10.26,22.85 10,22.57L5.1,18.37L5.84,17.6C6.03,17.39 6.3,17.28 6.58,17.28H6.8L10,19V9M11,5A4,4 0 0,1 15,9C15,10.5 14.2,11.77 13,12.46V11.24C13.61,10.69 14,9.89 14,9A3,3 0 0,0 11,6A3,3 0 0,0 8,9C8,9.89 8.39,10.69 9,11.24V12.46C7.8,11.77 7,10.5 7,9A4,4 0 0,1 11,5Z`,at=`M7,10L12,15L17,10H7Z`,ot=`M12,20C7.59,20 4,16.41 4,12C4,7.59 7.59,4 12,4C16.41,4 20,7.59 20,12C20,16.41 16.41,20 12,20M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M7,13H17V11H7`,st=`M14,3V5H17.59L7.76,14.83L9.17,16.24L19,6.41V10H21V3M19,19H5V5H12V3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V12H19V19Z`,ct=`M13 12.6L19 9.2V13C19.7 13 20.4 13.1 21 13.4V7.5C21 7.1 20.8 6.8 20.5 6.6L12.6 2.2C12.4 2.1 12.2 2 12 2S11.6 2.1 11.4 2.2L3.5 6.6C3.2 6.8 3 7.1 3 7.5V16.5C3 16.9 3.2 17.2 3.5 17.4L11.4 21.8C11.6 21.9 11.8 22 12 22S12.4 21.9 12.6 21.8L13.5 21.3C13.2 20.7 13.1 20 13 19.3M12 4.2L18 7.5L16 8.6L10.1 5.2L12 4.2M11 19.3L5 15.9V9.2L11 12.6V19.3M12 10.8L6 7.5L8 6.3L14 9.8L12 10.8M16.9 15.5L19 17.6L21.1 15.5L22.5 16.9L20.4 19L22.5 21.1L21.1 22.5L19 20.4L16.9 22.5L15.5 21.1L17.6 19L15.5 16.9L16.9 15.5Z`,lt=`M20.71,7.04C21.1,6.65 21.1,6 20.71,5.63L18.37,3.29C18,2.9 17.35,2.9 16.96,3.29L15.12,5.12L18.87,8.87M3,17.25V21H6.75L17.81,9.93L14.06,6.18L3,17.25Z`,ut=`M8,5.14V19.14L19,12.14L8,5.14Z`,dt=`M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z`,ft=`M17.65,6.35C16.2,4.9 14.21,4 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20C15.73,20 18.84,17.45 19.73,14H17.65C16.83,16.33 14.61,18 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6C13.66,6 15.14,6.69 16.22,7.78L13,11H20V4L17.65,6.35Z`,pt=`M12,4C14.1,4 16.1,4.8 17.6,6.3C20.7,9.4 20.7,14.5 17.6,17.6C15.8,19.5 13.3,20.2 10.9,19.9L11.4,17.9C13.1,18.1 14.9,17.5 16.2,16.2C18.5,13.9 18.5,10.1 16.2,7.7C15.1,6.6 13.5,6 12,6V10.6L7,5.6L12,0.6V4M6.3,17.6C3.7,15 3.3,11 5.1,7.9L6.6,9.4C5.5,11.6 5.9,14.4 7.8,16.2C8.3,16.7 8.9,17.1 9.6,17.4L9,19.4C8,19 7.1,18.4 6.3,17.6Z`,mt=`M12 21C8.2 20 5 15.5 5 11.2V6.3L12 3.2L19 6.3V12.1C19.7 12.2 20.3 12.4 20.9 12.7C21 12.1 21 11.6 21 11V5L12 1L3 5V11C3 16.5 6.8 21.7 12 23C12.4 22.9 12.7 22.8 13 22.7C12.6 22.2 12.2 21.6 12 21M18 14.5C19.1 14.5 20.1 14.9 20.8 15.7L22 14.5V18.5H18L19.8 16.7C19.3 16.3 18.7 16 18 16C16.6 16 15.5 17.1 15.5 18.5S16.6 21 18 21C18.8 21 19.5 20.6 20 20H21.7C21.1 21.5 19.7 22.5 18 22.5C15.8 22.5 14 20.7 14 18.5S15.8 14.5 18 14.5Z`,ht=`M23,12H17V10L20.39,6H17V4H23V6L19.62,10H23V12M15,16H9V14L12.39,10H9V8H15V10L11.62,14H15V16M7,20H1V18L4.39,14H1V12H7V14L3.62,18H7V20Z`,gt=`M12,17.27L18.18,21L16.54,13.97L22,9.24L14.81,8.62L12,2L9.19,8.62L2,9.24L7.45,13.97L5.82,21L12,17.27Z`,_t=`M20.8 22.7L17.9 19.8L18.2 21L12 17.3L5.8 21L7.4 14L2 9.2L6.9 8.8L1.1 3L2.4 1.7L22.1 21.4L20.8 22.7M22 9.2L14.8 8.6L12 2L10 6.8L16.9 13.7L22 9.2Z`,vt=`M12,15.39L8.24,17.66L9.23,13.38L5.91,10.5L10.29,10.13L12,6.09L13.71,10.13L18.09,10.5L14.77,13.38L15.76,17.66M22,9.24L14.81,8.63L12,2L9.19,8.63L2,9.24L7.45,13.97L5.82,21L12,17.27L18.18,21L16.54,13.97L22,9.24Z`,yt=`M3,17V19H9V17H3M3,5V7H13V5H3M13,21V19H21V17H13V15H11V21H13M7,9V11H3V13H7V15H9V9H7M21,13V11H11V13H21M15,9H17V7H21V5H17V3H15V9Z`,bt=`M9,16V10H5L12,3L19,10H15V16H9M5,20V18H19V20H5Z`,xt=`M16.36,14C16.44,13.34 16.5,12.68 16.5,12C16.5,11.32 16.44,10.66 16.36,10H19.74C19.9,10.64 20,11.31 20,12C20,12.69 19.9,13.36 19.74,14M14.59,19.56C15.19,18.45 15.65,17.25 15.97,16H18.92C17.96,17.65 16.43,18.93 14.59,19.56M14.34,14H9.66C9.56,13.34 9.5,12.68 9.5,12C9.5,11.32 9.56,10.65 9.66,10H14.34C14.43,10.65 14.5,11.32 14.5,12C14.5,12.68 14.43,13.34 14.34,14M12,19.96C11.17,18.76 10.5,17.43 10.09,16H13.91C13.5,17.43 12.83,18.76 12,19.96M8,8H5.08C6.03,6.34 7.57,5.06 9.4,4.44C8.8,5.55 8.35,6.75 8,8M5.08,16H8C8.35,17.25 8.8,18.45 9.4,19.56C7.57,18.93 6.03,17.65 5.08,16M4.26,14C4.1,13.36 4,12.69 4,12C4,11.31 4.1,10.64 4.26,10H7.64C7.56,10.66 7.5,11.32 7.5,12C7.5,12.68 7.56,13.34 7.64,14M12,4.03C12.83,5.23 13.5,6.57 13.91,8H10.09C10.5,6.57 11.17,5.23 12,4.03M18.92,8H15.97C15.65,6.75 15.19,5.55 14.59,4.44C16.43,5.07 17.96,6.34 18.92,8M12,2C6.47,2 2,6.5 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2Z`,St=`M3.55 19.09L4.96 20.5L6.76 18.71L5.34 17.29M12 6C8.69 6 6 8.69 6 12S8.69 18 12 18 18 15.31 18 12C18 8.68 15.31 6 12 6M20 13H23V11H20M17.24 18.71L19.04 20.5L20.45 19.09L18.66 17.29M20.45 5L19.04 3.6L17.24 5.39L18.66 6.81M13 1H11V4H13M6.76 5.39L4.96 3.6L3.55 5L5.34 6.81L6.76 5.39M1 13H4V11H1M13 20H11V23H13`,D=`M5.5 3h13A2.5 2.5 0 0 1 21 5.5v13a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 18.5v-13A2.5 2.5 0 0 1 5.5 3zM6 5A1 1 0 0 0 5 6v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1zM8 11.2 12 7.2l4 4-1.4 1.4L12 10l-2.6 2.6zM8 15.4l4-4 4 4-1.4 1.4-2.6-2.6-2.6 2.6z`,Ct=`shelly-elevate`;function*wt(e){for(let t of e.querySelectorAll(`*`))t.localName===`ha-icon`&&t.icon?.startsWith(`${Ct}:`)&&(yield t),t.shadowRoot&&(yield*wt(t.shadowRoot))}var Tt=()=>{let e=window;e.customIcons=e.customIcons??{},e.customIcons[Ct]??={getIcon:async()=>({path:D,viewBox:`0 0 24 24`}),getIconList:async()=>[{name:`display`}]},(async()=>{for(let e of wt(document)){if(!e._legacy)continue;let t=e.icon;e._legacy=!1,e.icon=void 0,await e.updateComplete,e.icon=t}})()};function O(e){"@babel/helpers - typeof";return O=typeof Symbol==`function`&&typeof Symbol.iterator==`symbol`?function(e){return typeof e}:function(e){return e&&typeof Symbol==`function`&&e.constructor===Symbol&&e!==Symbol.prototype?`symbol`:typeof e},O(e)}function Et(e,t){if(O(e)!=`object`||!e)return e;var n=e[Symbol.toPrimitive];if(n!==void 0){var r=n.call(e,t||`default`);if(O(r)!=`object`)return r;throw TypeError(`@@toPrimitive must return a primitive value.`)}return(t===`string`?String:Number)(e)}function Dt(e){var t=Et(e,`string`);return O(t)==`symbol`?t:t+``}function k(e,t,n){return(t=Dt(t))in e?Object.defineProperty(e,t,{value:n,enumerable:!0,configurable:!0,writable:!0}):e[t]=n,e}var A=e=>e.state===void 0,j=(e,t)=>e.find(e=>e.entry_id===t)?.name??t,Ot=e=>new Set([...e.per_device,...e.schema.filter(e=>e.per_device).map(e=>e.key)]),kt=`shellyelevateintegration`,At=class{constructor(e){k(this,`getHass`,void 0),this.getHass=e}get hass(){return this.getHass()}ws(e,t={}){return this.hass.callWS({type:`${kt}/${e}`,...t})}async devices(){return(await this.ws(`devices`)).devices}settingsGet(e){return this.ws(`settings/get`,{entry_id:e})}settingsSet(e,t){return this.ws(`settings/set`,{entry_id:e,changes:t})}subscribeSettings(e,t){return this.hass.connection.subscribeMessage(e=>t(e.changes),{type:`${kt}/settings/subscribe`,entry_id:e},{resubscribe:!0})}settingsExport(e,t){return this.ws(`settings/export`,{entry_id:e,include_secrets:t})}async settingsCopy(e,t,n){let r={source:e,targets:t};n?.length&&(r.keys=n);let i=await this.ws(`settings/copy`,r);return{results:i.results,errors:i.errors??{}}}async command(e,t,n={}){return(await this.ws(`command`,{entry_ids:e,action:t,params:n})).results}async backupsList(e){return(await this.ws(`backups/list`,e?{entry_id:e}:{})).backups}async backupsCreate(e,t){return(await this.ws(`backups/create`,t?{entry_id:e,name:t}:{entry_id:e})).backup}async backupsDiff(e,t,n){let r={entry_id:e,backup_id:t};return n&&(r.source_device_id=n),(await this.ws(`backups/diff`,r)).diff}async backupsRestore(e,t,n,r){let i={entry_id:e,backup_id:t};return n&&(i.keys=n),r&&(i.source_device_id=r),(await this.ws(`backups/restore`,i)).changes}async backupsDelete(e,t){await this.ws(`backups/delete`,{device_id:e,backup_id:t})}profilesList(){return this.ws(`profiles/list`)}async profilesSave(e){let t=Object.fromEntries(Object.entries(e).filter(([,e])=>e!==void 0));return(await this.ws(`profiles/save`,t)).profile_id}async profilesDelete(e){await this.ws(`profiles/delete`,{profile_id:e})}async profilesSetDefault(e){await this.ws(`profiles/set_default`,{profile_id:e})}async profilesApply(e,t,n){let r=await this.ws(`profiles/apply`,{profile_id:e,entry_ids:t,dry_run:n});return{results:r.results??{},errors:r.errors??{}}}installerInfo(){return this.ws(`installer/info`)}subscribeProvision(e,t,n){return this.hass.connection.subscribeMessage(n,{type:`${kt}/installer/provision`,host:e,...t,profile_id:t.profile_id||null,dashboard_url:t.dashboard_url?.trim()||null},{resubscribe:!1})}revertCheck(e){return this.ws(`revert/check`,{host:e})}subscribeRevert(e,t,n){return this.hass.connection.subscribeMessage(n,{type:`${kt}/revert/run`,host:e,...t},{resubscribe:!1})}},M=e=>{if(!e)return`Unknown error`;if(typeof e==`string`)return e;if(typeof e==`object`){let t=e;if(typeof t.message==`string`&&t.message)return t.message;if(typeof t.error==`string`&&t.error)return t.error;if(typeof t.code==`string`)return t.code}return String(e)},jt=[`ha-card`,`ha-button`,`ha-icon-button`,`ha-svg-icon`,`ha-switch`,`ha-checkbox`,`ha-input`,`ha-select`,`ha-dropdown`,`ha-dropdown-item`,`ha-alert`,`ha-spinner`,`ha-expansion-panel`,`ha-settings-row`,`ha-dialog`,`ha-dialog-header`,`ha-dialog-footer`,`ha-form`,`ha-list-base`,`ha-list-item-base`,`ha-list-item-button`,`ha-label`,`ha-menu-button`],Mt=[`hass-tabs-subpage`,`hass-tabs-subpage-data-table`,`ha-input-search`,`ha-generic-picker`,`ha-code-editor`,`ha-markdown`],Nt=[...jt,...Mt],N=e=>customElements.get(e)!==void 0,P=(e=Nt)=>e.filter(e=>!N(e)),Pt=e=>new Promise(t=>setTimeout(t,e)),F=(e,t)=>Promise.race([Promise.all(e.map(e=>customElements.whenDefined(e))),Pt(t)]),I=e=>N(e)?document.createElement(e).routerOptions?.routes??{}:{},L=async(e,t)=>{await Promise.allSettled(t.map(t=>e[t]?.load?.()))},Ft=async()=>{await F([`partial-panel-resolver`],5e3),N(`ha-panel-config`)||(await L(document.createElement(`partial-panel-resolver`)._getRoutes?.({config:{component_name:`config`,url_path:`config`}})?.routes??{},[`config`]),await F([`ha-panel-config`],5e3)),await L(I(`ha-panel-config`),[`devices`,`integrations`,`backup`,`automation`,`voice-assistants`]),await L(I(`ha-config-devices`),[`dashboard`]),await L(I(`ha-config-backup`),[`overview`,`backups`]),await L(I(`ha-config-automation`),[`dashboard`,`edit`]),await L(I(`ha-config-voice-assistants`),[`assistants`])},It=async()=>{let e=window;e.loadCardHelpers&&await(await e.loadCardHelpers()).createCardElement({type:`entities`,entities:[]}).constructor.getConfigElement?.()},Lt=null,Rt=()=>(Lt||=(async()=>{if(!P().length||(await F(P(),1500),!P().length))return[];try{await Ft()}catch(e){console.warn(`shelly-elevate: loading the config panel failed`,e)}if(P([`ha-form`]).length)try{await It()}catch(e){console.warn(`shelly-elevate: loading card helpers failed`,e)}await F(P(),3e3);let e=P();return e.length&&console.warn(`shelly-elevate: Home Assistant elements not available:`,e.join(`, `)),e})(),Lt),zt=async(e,t)=>{if(N(`ha-progress-bar`))return!0;if(!N(`ha-selector`))return!1;let n=document.createElement(`div`);n.style.display=`none`;let r=document.createElement(`ha-selector`);r.hass=e,r.selector={file:{accept:`.txt`}},n.appendChild(r),t.appendChild(n);try{await F([`ha-progress-bar`],8e3)}finally{n.remove()}return N(`ha-progress-bar`)},Bt=async()=>{if(N(`ha-filter-states`))return!0;try{N(`ha-config-devices`)||(N(`ha-panel-config`)||await Ft(),await L(I(`ha-panel-config`),[`devices`])),await L(I(`ha-config-devices`),[`dashboard`]),await F([`ha-filter-states`],3e3)}catch(e){console.warn(`shelly-elevate: loading the status filter failed`,e)}return N(`ha-filter-states`)},R=e=>e.currentTarget.value??``,z=e=>e.currentTarget.checked,B=e=>t=>{t.target===t.currentTarget&&e()},V=(e,t,n)=>{e.dispatchEvent(new CustomEvent(t,{detail:n,bubbles:!0,composed:!0}))},H=(e,t=!1)=>{t?history.replaceState(history.state,``,e):history.pushState(null,``,e),V(window,`location-changed`,{replace:t})},Vt=(e,t)=>V(e,`hass-notification`,t),Ht=null,Ut=async(e,t)=>{Ht||(Ht=e.callWS({type:`brands/access_token`}).then(e=>e.token).catch(()=>null),setTimeout(()=>Ht=null,18e5));let n=await Ht;if(!n)return``;let r=new URL(`/api/brands/integration/${t}/${e.themes?.darkMode?`dark_`:``}icon.png`,location.origin);return r.searchParams.set(`token`,n),r.toString()},Wt=async e=>{if(navigator.clipboard)try{await navigator.clipboard.writeText(e);return}catch{}let t=document.createElement(`textarea`);t.value=e,document.body.appendChild(t),t.select(),document.execCommand(`copy`),t.remove()},U=o`
  :host {
    font-family: var(--ha-font-family-body);
    -webkit-font-smoothing: var(--ha-font-smoothing);
    -moz-osx-font-smoothing: var(--ha-moz-osx-font-smoothing);
    font-size: var(--ha-font-size-m);
    font-weight: var(--ha-font-weight-normal);
    line-height: var(--ha-line-height-normal);
  }

  h1 {
    font-family: var(--ha-font-family-heading);
    -webkit-font-smoothing: var(--ha-font-smoothing);
    -moz-osx-font-smoothing: var(--ha-moz-osx-font-smoothing);
    font-size: var(--ha-font-size-2xl);
    font-weight: var(--ha-font-weight-normal);
    line-height: var(--ha-line-height-condensed);
  }

  a {
    color: var(--primary-color);
  }

  .secondary {
    color: var(--secondary-text-color);
  }

  .error {
    color: var(--error-color);
  }

  /* --- config page layout (ha-config-backup-overview) --- */
  .content {
    padding: 28px 20px 0;
    max-width: 690px;
    margin: 0 auto;
    gap: var(--ha-space-6);
    display: flex;
    flex-direction: column;
    margin-bottom: calc(72px + var(--safe-area-inset-bottom, 0px));
  }

  /* --- cards (ha-config-backup-settings / assist-pref) --- */
  p {
    color: var(--secondary-text-color);
  }
  .card-header {
    padding-bottom: 8px;
  }
  /* card content that ends with list rows (they bring their own padding) */
  .card-content.list {
    padding-bottom: 0;
  }
  .card-actions {
    display: flex;
    justify-content: flex-end;
  }
  /* icon buttons next to a card header (assist-pref) */
  .header-actions {
    position: absolute;
    right: 0px;
    inset-inline-end: 0px;
    inset-inline-start: initial;
    top: 24px;
    display: flex;
    flex-direction: row;
  }
  .header-actions > * {
    margin-top: -16px;
    margin-right: 8px;
    margin-inline-end: 8px;
    margin-inline-start: initial;
    color: var(--secondary-text-color);
  }

  /* --- lists in cards (ha-backup-overview-backups / ha-backup-config-schedule) --- */
  ha-list-item-button::part(start),
  ha-list-item-base::part(start) {
    color: var(--ha-color-text-secondary, var(--secondary-text-color));
  }
  /* A "⋮" button at the end of a list row: its 48px target overlaps the row padding so the row
     keeps the height of stock rows with a 24px end icon (ha-backup-overview-backups: 66px). */
  ha-list-item-button > ha-dropdown[slot="end"] > ha-icon-button,
  ha-list-item-base > ha-dropdown[slot="end"] > ha-icon-button {
    margin-block: calc(var(--ha-space-3) * -1);
  }
  ha-list-base.rows {
    --ha-row-item-padding-inline: 0;
  }
  ha-list-base.rows ha-list-item-base::part(headline),
  ha-list-base.rows ha-list-item-base::part(supporting-text) {
    white-space: wrap;
  }
  ha-dropdown {
    font-size: var(--ha-font-size-m);
    font-family: var(--ha-font-family-body);
    letter-spacing: normal;
  }

  ha-alert,
  ha-input,
  ha-select,
  ha-input-search {
    display: block;
  }

  .hidden {
    display: none !important;
  }

  .loading {
    display: flex;
    justify-content: center;
    padding: var(--ha-space-4);
  }

  /* Native textarea fallback when ha-code-editor is unavailable */
  textarea.fallback {
    box-sizing: border-box;
    width: 100%;
    min-height: 280px;
    font-family: var(--ha-font-family-code);
    font-size: var(--ha-font-size-s);
    color: var(--primary-text-color);
    background: var(--secondary-background-color);
    border: 1px solid var(--divider-color);
    border-radius: var(--ha-border-radius-md);
    padding: var(--ha-space-2);
  }
`,W=o`
  /* stock dialogs (dialog-box, dialog-generate-backup) have no haStyle: normal line height */
  ha-dialog {
    line-height: normal;
  }
  .dialog-text {
    margin: 0 0 var(--ha-space-4);
    color: var(--primary-text-color);
  }
  .dialog-text.secondary {
    color: var(--secondary-text-color);
  }
  .stack {
    display: flex;
    flex-direction: column;
    gap: var(--ha-space-4);
  }
`,Gt=null,Kt=e=>{Gt=e},qt=e=>e.isConnected||!Gt?.isConnected?e:Gt,G=(e,t)=>{customElements.get(e)||customElements.define(e,t)},K=(e,t)=>new Promise(n=>{if(qt(e).dispatchEvent(new CustomEvent(`se-confirm`,{detail:{...t,resolve:n},bubbles:!0,composed:!0,cancelable:!0}))){let e=typeof t.text==`string`?t.text:``;n(window.confirm(`${t.title}\n\n${e}\n${(t.items??[]).join(`
`)}`))}}),q=(e,t,n=`info`,r)=>{let i=n===`error`?1e4:r?.length?8e3:4e3;Vt(qt(e),{message:t,duration:i,dismissable:!0,action:r?.length?{text:`Details`,action:()=>{K(e,{title:t,items:r,alert:!0})}}:void 0})},J=(e,t,n)=>q(e,t?`${t}: ${M(n)}`:M(n),`error`),Y=(e,t,n)=>V(e,`se-open-tab`,{tab:t,entryId:n}),Jt=e=>V(e,`se-refresh-devices`),Yt=(e,t={})=>V(e,`se-revert`,t),Xt={24:`7.0`,25:`7.1`,26:`8.0`,27:`8.1`,28:`9`,29:`10`,30:`11`,31:`12`,32:`12L`,33:`13`,34:`14`,35:`15`,36:`16`},Zt=e=>{if(typeof e!=`number`)return``;let t=Xt[e];return t?`Android ${t} (API ${e})`:`Android API ${e}`},Qt=(e,t)=>V(e,`se-entry-selected`,{entryId:t}),$t=(e,t)=>tn(e,new Blob([JSON.stringify(t,null,2)],{type:`application/json`})),en=(e,t)=>tn(e,new Blob([t],{type:`text/plain`})),tn=(e,t)=>{let n=URL.createObjectURL(t),r=document.createElement(`a`);r.href=n,r.download=e,document.body.appendChild(r),r.click(),r.remove(),setTimeout(()=>URL.revokeObjectURL(n),1e3)},nn=e=>new Promise(t=>{let n=document.createElement(`input`);n.type=`file`,n.accept=e,n.addEventListener(`change`,()=>t(n.files?.[0]??null),{once:!0}),n.addEventListener(`cancel`,()=>t(null),{once:!0}),n.click()}),rn=e=>e.toLowerCase().replace(/[^a-z0-9]+/g,`-`).replace(/^-+|-+$/g,``)||`display`,X=(e,t)=>{if(!e)return`–`;let n=new Date(e);return Number.isNaN(n.getTime())?e:n.toLocaleString(t||void 0,{dateStyle:`medium`,timeStyle:`short`})},an=e=>e===void 0?`–`:e===null?`null`:e===`**REDACTED**`?`••••`:typeof e==`string`?e===``?`""`:e:JSON.stringify(e),Z=(e,t,n=`${t}s`)=>`${e} ${e===1?t:n}`,on=e=>typeof e==`object`&&!!e&&!Array.isArray(e),Q=e=>e.stopPropagation(),sn=e=>(...t)=>({_$litDirective$:e,values:t}),cn=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,n){this._$Ct=e,this._$AM=t,this._$Ci=n}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}},{I:ln}=Le,un={},dn=(e,t=un)=>e._$AH=t,fn=sn(class extends cn{constructor(){super(...arguments),this.key=b}render(e,t){return this.key=e,t}update(e,[t,n]){return t!==this.key&&(dn(e),this.key=t),n}}),pn={done:qe,failed:Ue,warning:He,skipped:ot,pending:Ye},mn=class extends w{constructor(){super(),this.steps=[]}render(){return v`
      <ha-list-base aria-label="Installation steps">
        ${this.steps.map(e=>fn(!!e.detail,v`<ha-list-item-base class=${e.status}>
              <span slot="start" class="ico">
                ${e.status===`running`?v`<ha-spinner size="tiny"></ha-spinner>`:v`<ha-svg-icon .path=${pn[e.status]}></ha-svg-icon>`}
              </span>
              <span slot="headline">${e.label}</span>
              ${e.detail?v`<span slot="supporting-text" class="detail">${e.detail}</span>`:b}
            </ha-list-item-base>`))}
      </ha-list-base>
    `}};k(mn,`properties`,{steps:{attribute:!1}}),k(mn,`styles`,[U,o`
      :host {
        display: block;
      }
      .ico {
        display: inline-flex;
        width: 24px;
        justify-content: center;
      }
      .done ha-svg-icon {
        color: var(--success-color);
      }
      .failed ha-svg-icon {
        color: var(--error-color);
      }
      .warning ha-svg-icon {
        color: var(--warning-color);
      }
      .pending ha-svg-icon,
      .skipped ha-svg-icon {
        color: var(--disabled-text-color);
      }
      .pending [slot="headline"],
      .skipped [slot="headline"] {
        color: var(--secondary-text-color);
      }
      .detail {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }
      .failed .detail {
        color: var(--error-color);
      }
    `]),G(`sep-step-list`,mn);var hn=e=>{let t=`$ ${e}`;return t.length>240?{kind:`command`,text:`${t.slice(0,200)} … ${t.slice(-30)}`,full:t}:{kind:`command`,text:t}},gn=e=>e.map(e=>e.full??e.text).join(`
`),_n=class extends w{constructor(){super(),k(this,`_follow`,!0),this.lines=[]}_onScroll(e){let t=e.currentTarget;this._follow=t.scrollHeight-t.scrollTop-t.clientHeight<24}updated(e){if(e.has(`lines`)&&this._follow){let e=this.renderRoot.querySelector(`.error-log`);e&&(e.scrollTop=e.scrollHeight)}}render(){return v`<div class="error-log" role="log" @scroll=${this._onScroll}>
      ${this.lines.length?v`<pre class="wrap">${this.lines.map(e=>v`<div class=${e.kind}>${e.text}</div>`)}</pre>`:v`<div>Waiting for the first step…</div>`}
    </div>`}};k(_n,`properties`,{lines:{attribute:!1}}),k(_n,`styles`,o`
    :host {
      display: block;
    }
    /* error-log-card */
    .error-log {
      position: relative;
      font-family: var(--ha-font-family-code);
      text-align: start;
      padding: var(--ha-space-4);
      overflow: auto;
      max-height: 320px;
      border-top: 1px solid var(--divider-color);
      direction: ltr;
      color: var(--primary-text-color);
    }
    /* ha-ansi-to-html */
    pre {
      margin: 0;
    }
    pre.wrap {
      white-space: pre-wrap;
      overflow-wrap: break-word;
    }
    .error {
      color: var(--error-color);
    }
    .warning {
      color: var(--warning-color);
    }
  `),G(`sep-install-log`,_n);var vn={adb_connect:`Connect over ADB`,check:`Check the display`,mqtt_cleanup:`Remove the MQTT discovery entries`,stop_app:`Stop Shelly Elevate`,enable_stock:`Enable the stock Shelly app`,stock_overlay:`Let the stock Shelly app draw on top again`,stock_home:`Make the stock Shelly app the home app`,doze_whitelist:`Remove the battery optimisation exemption`,app_ops:`Reset the special app permissions`,brightness_mode:`Restore the brightness mode`,brightness:`Restore the screen brightness`,uninstall:`Uninstall Shelly Elevate`,remove_system_copy:`Remove the copy in /system`,hide_system_copy:`Hide the copy in /system`,uninstall_v1:`Uninstall the old Shelly Elevate V1 app`,uninstall_launcher:`Uninstall Ultra Small Launcher`,cleanup:`Clean up`,start_stock:`Start the stock Shelly app`,verify:`Check the result`,remove_entry:`Remove from Home Assistant`,reboot:`Restart the display`,adb_key:`Remove Home Assistant's ADB key`,adb_tcp:`Stop ADB on port 5555 after a restart`,adb_wifi:`Turn off ADB over Wi‑Fi`,dev_settings:`Turn off the developer settings`,adb_enabled:`Turn off ADB debugging`},yn=Object.keys(vn),bn=new Set([`adb_connect`,`check`,`remove_entry`]),xn={wifi_by_app:{title:`The display will go offline`,text:`The display's Wi‑Fi network was set up in Shelly Elevate. Uninstalling the app removes it, and the display loses its connection. To keep it online, set up Wi‑Fi again in the Shelly settings under Network first.`},stock_needs_root:{title:`The stock Shelly app stays disabled`,text:`It was disabled with root access, and this display is not rooted, so it cannot be enabled again. The display may be left without a home app.`},system_copy_needs_root:{title:`A copy of Shelly Elevate stays in /system`,text:`It can only be removed on a rooted display. It is hidden and its data is deleted instead.`},stock_missing:{title:`The stock Shelly app is not installed`,text:`After the revert, the display has no home app.`},no_baseline:{title:`Screen settings stay as they are`,text:`Shelly Elevate was not installed on this display by this Home Assistant, so the original brightness settings are not known.`,type:`info`}},Sn={app:`Shelly Elevate is still installed.`,system_copy:`A copy of Shelly Elevate is still in /system. It can only be removed on a rooted display.`,stock_disabled:`The stock Shelly app is still disabled. It can only be enabled again on a rooted display.`},Cn={remove_entry:[`Remove from Home Assistant`,`Removes the display and its entities once the app is gone.`],remove_wiki_launcher:[`Remove Ultra Small Launcher`,`The home app from the community guide. It is removed once the stock Shelly app is the home app again.`],reboot:[`Restart the display`,`Restarts the display at the end.`],disable_adb:[`Turn off ADB over Wi‑Fi`,`Turns off ADB debugging and ADB over Wi‑Fi as the very last step. Home Assistant can then no longer reach the display over ADB.`]},wn=`Not possible when ADB is turned off: Home Assistant loses ADB access at the end. Restart the display yourself afterwards.`,Tn=new Set([`done`,`failed`,`warning`,`skipped`]),En=/^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?!$)|$)){4}$|^[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?$/,Dn={remove_entry:!0,reboot:!0,disable_adb:!1,remove_wiki_launcher:!0,accept_wifi_loss:!1},On=(e,t)=>{let n=e.check,r=e.platform.root,i=[`adb_connect`,`check`,`stop_app`];return n.stock_installed&&(i.push(`enable_stock`,`stock_overlay`),n.stock_home&&i.push(`stock_home`)),i.push(`doze_whitelist`,`app_ops`),n.app_installed&&i.push(`uninstall`),(n.priv_app||n.init_rc)&&(r?i.push(`remove_system_copy`):n.priv_app&&i.push(`hide_system_copy`)),n.legacy_v1&&i.push(`uninstall_v1`),n.wiki_launcher&&t.remove_wiki_launcher&&n.stock_installed&&i.push(`uninstall_launcher`),i.push(`cleanup`),n.stock_installed&&i.push(`start_stock`),i.push(`verify`),e.entry_id&&t.remove_entry&&i.push(`remove_entry`),t.disable_adb?(r&&i.push(`adb_key`),i.push(`adb_tcp`,`adb_wifi`,`dev_settings`,`adb_enabled`)):t.reboot&&i.push(`reboot`),i},kn=(e,t)=>{let n=e.check,r=e.platform.root,i=[];return n.app_installed&&i.push(`Uninstall Shelly Elevate`),(n.priv_app||n.init_rc)&&i.push(r||!n.priv_app?`Remove the copy of Shelly Elevate in /system`:`Hide the copy of Shelly Elevate in /system and delete its data`),n.legacy_v1&&i.push(`Uninstall the old Shelly Elevate V1 app`),n.wiki_launcher&&n.stock_installed&&t.remove_wiki_launcher&&i.push(`Uninstall Ultra Small Launcher`),n.stock_installed&&!(n.stock_disabled&&n.stock_disabled_by_root&&!r)&&(n.stock_disabled&&i.push(`Enable the stock Shelly app again`),i.push(n.stock_home?`Make the stock Shelly app the home app and start it`:`Let the stock Shelly app draw on top again and start it`)),i.push(`Reset the permissions and the battery optimisation exemption Shelly Elevate was given`),e.warnings.includes(`no_baseline`)||i.push(`Restore the original screen brightness settings`),n.leftover_apk&&i.push(`Delete the installation file left on the display`),i},An=(e,t)=>{if(e.error)return String(e.error);switch(`${e.step}:${e.status}`){case`check:done`:return[e.root===!1?`Not rooted`:e.root===!0?`Rooted`:``,Zt(e.sdk)].filter(Boolean).join(` · `)||t;case`verify:done`:return`Nothing left`;case`verify:failed`:return e.remaining?.length?e.remaining.map(e=>Sn[e]??e).join(` `):t;case`adb_enabled:done`:return`The ADB connection was closed`;default:return t}},jn=class extends w{constructor(){super(),k(this,`_unsub`,null),k(this,`_cancelled`,!1),k(this,`_checkSeq`,0),k(this,`_closed`,B(()=>{this._open=!1,this._checkSeq++})),this.devices=[],this._open=!1,this._stage=`host`,this._host=``,this._target={},this._check=null,this._checkError=``,this._opts={...Dn},this._steps=[],this._log=[],this._error=``,this._result=null,this._stepsOpen=!1,this._logOpen=!1,this._hasProgressBar=N(`ha-progress-bar`)}show(e={}){this._stage===`running`&&this._open||(this._target=e,this._host=e.host??e.prefill??``,this._resetRun(),this._check=null,this._checkError=``,this._opts={...Dn},this._open=!0,e.host?this._runCheck():this._stage=`host`)}willUpdate(e){e.has(`_open`)&&this._open&&!this._hasProgressBar&&this.api&&zt(this.api.hass,this.renderRoot).then(e=>this._hasProgressBar=e)}_close(){this._open=!1,this._checkSeq++}get _name(){return this._check?.name??this._target.name??this._host}_resetRun(){this._cancelled=!1,this._steps=[],this._log=[],this._error=``,this._result=null,this._stepsOpen=!1,this._logOpen=!1}async _runCheck(){let e=this._host.trim();if(!En.test(e))return;this._host=e,this._stage=`checking`,this._checkError=``;let t=++this._checkSeq;try{let n=await this.api.revertCheck(e);if(t!==this._checkSeq)return;this._check=n,this._opts={...Dn,remove_entry:!!n.entry_id},this._stage=`confirm`}catch(e){if(t!==this._checkSeq)return;this._checkError=M(e),this._stage=`confirm`}}async _start(){let e=this._check;if(!e||e.warnings.includes(`wifi_by_app`)&&!this._opts.accept_wifi_loss)return;this._resetRun(),this._stage=`running`,this._steps=On(e,this._opts).map(e=>({id:e,label:vn[e]??e,status:`pending`}));let t={...this._opts,remove_entry:!!e.entry_id&&this._opts.remove_entry,reboot:!this._opts.disable_adb&&this._opts.reboot,accept_wifi_loss:e.warnings.includes(`wifi_by_app`)&&this._opts.accept_wifi_loss};try{this._unsub=await this.api.subscribeRevert(this._host,t,e=>this._event(e))}catch(e){this._stage=`error`,this._error=M(e)}}async _stopSubscription(){let e=this._unsub;if(this._unsub=null,e)try{await e()}catch{}}async _askCancel(){await K(this,{title:`Stop reverting?`,text:`The running step is stopped. The display may be left partly reverted; you can run the revert again.`,confirmText:`Stop`,dismissText:`Keep reverting`,destructive:!0})&&this._stage===`running`&&(await this._stopSubscription(),this._cancelled=!0,this._addLog({kind:`error`,text:`Cancelled`}),this._failRunning(`Cancelled`),this._stage=`error`,this._error=``)}_addLog(...e){this._log=[...this._log,...e]}_failRunning(e){this._steps=this._steps.map(t=>t.status===`running`?{...t,status:`failed`,detail:t.detail||e}:t)}_stepIndex(e,t){let n=e.findIndex(e=>e.id===t);if(n>=0)return n;let r=yn.indexOf(t),i=e.findIndex(e=>yn.indexOf(e.id)>r);return(r<0||i<0)&&(i=e.length),e.splice(i,0,{id:t,label:vn[t]??t,status:`pending`}),i}_step(e){let t=[...this._steps],n=this._stepIndex(t,e.step),r=t[n];if(e.status===`running`)this._addLog(e.command?hn(e.command):{kind:`info`,text:`# ${r.label}`});else if(e.status===`failed`)this._addLog({kind:bn.has(e.step)?`error`:`warning`,text:e.error?String(e.error):An(e)??`failed`});else if(e.status===`done`){let t=e.output?.replace(/\r/g,``).trimEnd();t&&this._addLog(...t.split(`
`).map(e=>({kind:`output`,text:e})))}if(t[n]={...r,status:e.status===`failed`&&!bn.has(e.step)?`warning`:e.status,detail:An(e,r.detail)},e.status===`running`)for(let e=0;e<n;e++)t[e].status===`pending`&&(t[e]={...t[e],status:`skipped`});this._steps=t,e.step===`remove_entry`&&e.status===`done`&&Jt(this)}_event(e){switch(e.type){case`step`:this._step(e);break;case`done`:this._addLog({kind:`info`,text:`# Finished`}),this._result=e,this._steps=this._steps.map(e=>e.status===`pending`?{...e,status:`skipped`}:e),this._steps.some(e=>e.status===`warning`)&&(this._stepsOpen=!0),this._stage=`done`,this._stopSubscription(),e.entry_removed&&Jt(this),this._open||q(this,e.remaining.length?`${this._name} was partly reverted`:`${this._name} was reverted to stock`,e.remaining.length?`warning`:`success`);break;case`error`:this._log.at(-1)?.text!==e.error&&this._addLog({kind:`error`,text:`Error: ${e.error}`}),this._failRunning(e.error),this._error=e.error,this._stage=`error`,this._stopSubscription()}}async _copyLog(e){e.stopPropagation(),await Wt(gn(this._log)),q(this,`Copied to clipboard`)}_downloadLog(e){e.stopPropagation();let t=new Date().toISOString().slice(0,19).replace(/[:T]/g,`-`);en(`shelly-elevate-revert-${this._host||`display`}-${t}.txt`,`${gn(this._log)}\n`)}_title(){switch(this._stage){case`host`:return`Revert a display to stock`;case`checking`:case`confirm`:return this._checkError?`Could not check the display`:`Revert ${this._name} to stock?`;case`running`:return`Reverting ${this._name}`;case`done`:return this._result?.remaining.length?`Partly reverted`:`Reverted to stock`;default:return this._cancelled?`Revert cancelled`:`Revert failed`}}_subtitle(){if(this._stage===`host`)return;let e=this._name;return this._stage===`done`||this._stage===`error`?e===this._host?this._host:`${e} · ${this._host}`:e===this._host?void 0:this._host}_renderHost(){let e=!!this._host&&!En.test(this._host);return v`
      <p class="dialog-text">
        Removes Shelly Elevate from a display and gives it back to the stock Shelly app. Home Assistant connects over ADB
        (port 5555) and first checks what is installed; nothing is changed until you confirm.
      </p>
      <ha-input
        label="IP address of the display"
        placeholder="192.168.1.50"
        inputmode="decimal"
        autocomplete="off"
        autofocus
        .value=${this._host}
        .invalid=${e}
        .validationMessage=${e?`Enter an IP address or host name`:``}
        @input=${e=>this._host=R(e).trim()}
        @keydown=${e=>e.key===`Enter`&&this._runCheck()}
      ></ha-input>
    `}_renderChecking(){return v`<div class="centered">
      <ha-spinner></ha-spinner>
      <p>Checking what is installed on ${this._host}…</p>
    </div>`}_optionsSchema(e){let t=[];return e.entry_id&&t.push({name:`remove_entry`,selector:{boolean:{}}}),e.check.wiki_launcher&&e.check.stock_installed&&t.push({name:`remove_wiki_launcher`,selector:{boolean:{}}}),t.push({name:`reboot`,selector:{boolean:{}},disabled:this._opts.disable_adb}),t.push({name:`disable_adb`,selector:{boolean:{}}}),t}_renderConfirm(){if(this._checkError)return v`<ha-alert alert-type="error">${this._checkError}</ha-alert>
        <p class="dialog-text secondary hint">
          ADB debugging and ADB over Wi‑Fi (port 5555) must be on in the Android developer options of the display;
          on newer Shelly firmware also ADB - WiFi in the Shelly developer settings.
        </p>`;let e=this._check;if(!e)return b;let t=e.check,n=[e.platform.model,Zt(e.platform.sdk),e.platform.root?`Rooted`:`Not rooted`].filter(Boolean),r=!t.app_installed&&!t.priv_app&&!t.init_rc&&!t.legacy_v1,i={...this._opts,reboot:this._opts.reboot&&!this._opts.disable_adb};return v`
      <p class="dialog-text">
        ${r?v`Shelly Elevate is not installed on this display. Reverting restores what an installation changed and gives the
              display back to the stock Shelly app.`:v`Home Assistant removes Shelly Elevate from ${this._name} over ADB and gives the display back to the stock
              Shelly app.`}
      </p>
      <p class="dialog-text secondary platform">${n.join(` · `)}</p>
      ${e.warnings.map(e=>this._renderWarning(e))}
      <p class="dialog-text">This will:</p>
      <ul class="items">
        ${kn(e,this._opts).map(e=>v`<li>${e}</li>`)}
      </ul>
      <ha-form
        .hass=${this.api.hass}
        .data=${i}
        .schema=${this._optionsSchema(e)}
        .computeLabel=${e=>Cn[e.name]?.[0]??e.name}
        .computeHelper=${e=>e.name===`reboot`&&this._opts.disable_adb?wn:Cn[e.name]?.[1]}
        @value-changed=${e=>{e.stopPropagation();let t=e.detail.value;this._opts={...this._opts,remove_entry:!!t.remove_entry,remove_wiki_launcher:!!t.remove_wiki_launcher,disable_adb:!!t.disable_adb,reboot:t.disable_adb?this._opts.reboot:!!t.reboot}}}
      ></ha-form>
    `}_renderWarning(e){let t=xn[e];return t?e===`wifi_by_app`?v`<ha-alert alert-type="error" .title=${t.title}>${t.text}</ha-alert>
      <ha-checkbox
        class="accept"
        .checked=${this._opts.accept_wifi_loss}
        @change=${e=>this._opts={...this._opts,accept_wifi_loss:z(e)}}
        >I understand that the display goes offline</ha-checkbox
      >`:v`<ha-alert alert-type=${t.type??`warning`} .title=${t.title}>${t.text}</ha-alert>`:v`<ha-alert alert-type="warning">${e}</ha-alert>`}_renderProgressBar(){let e=this._steps,t=e.filter(e=>Tn.has(e.status)).length,n=e.find(e=>e.status===`running`),r=this._stage===`done`?100:e.length?Math.round(t/e.length*100):0,i;if(this._stage===`done`){let t=e.filter(e=>e.status===`warning`).length;i=t?`Finished – ${Z(t,`step`)} did not work`:`Finished`}else if(this._stage===`error`){let t=e.findIndex(e=>e.status===`failed`),n=this._cancelled?`Cancelled`:`Failed`;i=t>=0?`${n} at step ${t+1} of ${e.length}: ${e[t].label}`:n}else i=`Step ${Math.min(t+1,e.length)} of ${e.length}: ${n?.label??`Starting…`}`;return v`
      ${this._hasProgressBar?v`<ha-progress-bar .value=${r} ?loading=${this._stage===`running`} aria-label="Revert progress"></ha-progress-bar>`:v`<progress max="100" .value=${r}></progress>`}
      <p class="status" role="status">${i}</p>
    `}_renderResult(){let e=this._result;if(this._stage===`error`)return this._cancelled?v`<ha-alert alert-type="warning" title="Revert cancelled">
            The display may be partly reverted. You can run the revert again.
          </ha-alert>`:v`<ha-alert alert-type="error" title="Revert failed">${this._error}</ha-alert>`;if(this._stage===`running`)return v`<ha-alert alert-type="info">Keep this page open until the revert has finished.</ha-alert>`;if(!e)return b;let t=[];return e.entry_removed&&t.push(`${this._name} was removed from Home Assistant.`),e.adb_disabled?t.push(`ADB over Wi‑Fi is turned off. Restart the display to finish.`):this._steps.find(e=>e.id===`reboot`)?.status===`done`&&t.push(`The display is restarting.`),e.remaining.length?v`<ha-alert alert-type="warning" title="Not everything could be reverted">
      <ul class="remaining">
        ${e.remaining.map(e=>v`<li>${Sn[e]??e}</li>`)}
      </ul>
      ${t.join(` `)}
    </ha-alert>`:v`<ha-alert alert-type="success" title="The stock Shelly app is back">
        ${this._check&&!this._check.check.app_installed&&!this._check.check.priv_app?`Shelly Elevate was not installed; what an installation changes was reset.`:`Shelly Elevate was removed from the display.`}
        ${t.join(` `)}
      </ha-alert>`}_renderProgress(){let e=this._steps.filter(e=>Tn.has(e.status)&&e.status!==`failed`).length;return v`
      ${this._renderProgressBar()} ${this._renderResult()}
      <div class="panels">
        <ha-expansion-panel
          outlined
          .header=${`Steps`}
          .secondary=${`${e} of ${this._steps.length} done`}
          .expanded=${this._stepsOpen}
          @expanded-changed=${e=>{e.stopPropagation(),this._stepsOpen=e.detail.expanded}}
        >
          <sep-step-list .steps=${this._steps}></sep-step-list>
        </ha-expansion-panel>
        <ha-expansion-panel
          class="log"
          outlined
          .header=${`Log`}
          .secondary=${`${this._log.length} ${this._log.length===1?`line`:`lines`}`}
          .expanded=${this._logOpen}
          @expanded-changed=${e=>{e.stopPropagation(),this._logOpen=e.detail.expanded}}
        >
          <ha-icon-button
            slot="icons"
            .label=${`Copy to clipboard`}
            .path=${$e}
            ?disabled=${!this._log.length}
            @click=${this._copyLog}
            @keydown=${Q}
          ></ha-icon-button>
          <ha-icon-button
            slot="icons"
            .label=${`Download log`}
            .path=${E}
            ?disabled=${!this._log.length}
            @click=${this._downloadLog}
            @keydown=${Q}
          ></ha-icon-button>
          <sep-install-log .lines=${this._log}></sep-install-log>
        </ha-expansion-panel>
      </div>
    `}_renderBody(){switch(this._stage){case`host`:return this._renderHost();case`checking`:return this._renderChecking();case`confirm`:return this._renderConfirm();default:return this._renderProgress()}}_renderFooter(){let e=v`<ha-button slot="secondaryAction" appearance="plain" @click=${this._close}>Cancel</ha-button>`;switch(this._stage){case`host`:return v`${e}
          <ha-button slot="primaryAction" ?disabled=${!En.test(this._host)} @click=${this._runCheck}>Check display</ha-button>`;case`checking`:return e;case`confirm`:return this._checkError||!this._check?v`<ha-button
              slot="secondaryAction"
              appearance="plain"
              @click=${()=>this._target.host?this._close():this._stage=`host`}
              >${this._target.host?`Close`:`Back`}</ha-button
            >
            <ha-button slot="primaryAction" @click=${this._runCheck}>Try again</ha-button>`:v`${e}
          <ha-button slot="primaryAction" variant="danger" ?disabled=${this._check.warnings.includes(`wifi_by_app`)&&!this._opts.accept_wifi_loss} @click=${this._start}>Revert to stock</ha-button>`;case`running`:return v`<ha-button slot="secondaryAction" appearance="plain" variant="danger" @click=${this._askCancel}
          >Cancel</ha-button
        >`;case`done`:return v`<ha-button slot="primaryAction" @click=${this._close}>Close</ha-button>`;default:return v`<ha-button slot="secondaryAction" appearance="plain" @click=${this._close}>Close</ha-button>
          <ha-button slot="primaryAction" @click=${this._runCheck}>Try again</ha-button>`}}render(){let e=this._stage===`running`;return v`
      <ha-dialog
        .open=${this._open}
        .headerTitle=${this._title()}
        .headerSubtitle=${this._subtitle()}
        .preventScrimClose=${this._stage!==`host`&&this._stage!==`checking`}
        @closed=${this._closed}
      >
        ${e?v`<span slot="headerNavigationIcon"></span>`:b}
        <div class="revert">${this._renderBody()}</div>
        <ha-dialog-footer slot="footer">${this._renderFooter()}</ha-dialog-footer>
      </ha-dialog>
    `}};k(jn,`properties`,{api:{attribute:!1},devices:{attribute:!1},_open:{state:!0},_stage:{state:!0},_host:{state:!0},_target:{state:!0},_check:{state:!0},_checkError:{state:!0},_opts:{state:!0},_steps:{state:!0},_log:{state:!0},_error:{state:!0},_result:{state:!0},_stepsOpen:{state:!0},_logOpen:{state:!0},_hasProgressBar:{state:!0}}),k(jn,`styles`,[U,W,o`
      /* dialog-restore-backup */
      .centered {
        display: flex;
        flex-direction: column;
        align-items: center;
      }
      .centered ha-spinner {
        margin-bottom: var(--ha-space-4);
      }
      .centered p {
        margin: 0;
        color: var(--primary-text-color);
      }
      .platform,
      .hint {
        margin-top: calc(var(--ha-space-2) * -1);
      }
      ha-alert {
        margin-bottom: var(--ha-space-4);
      }
      ha-checkbox.accept {
        display: block;
        margin: calc(var(--ha-space-2) * -1) 0 var(--ha-space-4);
      }
      /* the bullet list of dialog-box (see the panel's confirm dialog) */
      .items {
        margin: calc(var(--ha-space-2) * -1) 0 var(--ha-space-4);
        padding-inline-start: var(--ha-space-5);
        color: var(--primary-text-color);
      }
      .items li {
        margin-bottom: var(--ha-space-1);
      }
      .remaining {
        margin: 0 0 var(--ha-space-1);
        padding-inline-start: var(--ha-space-5);
      }
      ha-form {
        display: block;
      }
      ha-progress-bar,
      progress {
        display: block;
        width: 100%;
      }
      p.status {
        margin: var(--ha-space-2) 0 var(--ha-space-4);
        color: var(--secondary-text-color);
      }
      .panels {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-2);
      }
      sep-step-list {
        --ha-row-item-padding-inline: 0;
      }
      ha-expansion-panel.log {
        --expansion-panel-content-padding: 0;
      }
      sep-install-log {
        line-height: var(--ha-line-height-normal);
      }
      ha-expansion-panel ha-icon-button {
        color: var(--secondary-text-color);
        margin: -8px 0;
      }
    `]),G(`sep-revert-dialog`,jn);var Mn=async(e,t,n)=>{let r=t.detail.item.value;r===`reload`?await n?.onReload?.()!==!1&&Jt(e):r===`integration`?H(`/config/integrations/integration/shellyelevateintegration`):n?.onSelect?.(r)},Nn=(e,t)=>v`<ha-dropdown
  slot="toolbar-icon"
  placement="bottom-end"
  @wa-select=${n=>Mn(e,n,t)}
>
  <ha-icon-button slot="trigger" .label=${`Menu`} .path=${T}></ha-icon-button>
  ${t?.items?v`${t.items}<wa-divider></wa-divider>`:b}
  <ha-dropdown-item value="reload">
    <ha-svg-icon slot="icon" .path=${ft}></ha-svg-icon>
    Reload
  </ha-dropdown-item>
  <ha-dropdown-item value="integration">
    <ha-svg-icon slot="icon" .path=${Ze}></ha-svg-icon>
    Integration settings
  </ha-dropdown-item>
</ha-dropdown>`,Pn=(e,t,n,r=b,i)=>{let a=r!==b;if(N(`hass-tabs-subpage`))return v`
      <hass-tabs-subpage main-page .hass=${t.hass} .route=${t.route} .tabs=${t.tabs} ?has-fab=${a}>
        <span slot="header" class="header">Shelly Elevate</span>
        ${Nn(e,i)}
        ${n} ${r}
      </hass-tabs-subpage>
    `;let o=`${t.route.prefix}${t.route.path}`;return v`
    <div class="fb-page">
      <div class="fb-toolbar">
        <ha-menu-button .hass=${t.hass} .narrow=${t.narrow}></ha-menu-button>
        <div class="fb-title">Shelly Elevate</div>
        ${Nn(e,i)}
      </div>
      <nav class="fb-tabs">
        ${t.tabs.map(e=>v`<a
            href=${e.path}
            class=${e.path===o?`active`:``}
            @click=${t=>{t.preventDefault(),H(e.path,!0)}}
            ><ha-svg-icon .path=${e.iconPath}></ha-svg-icon><span>${e.name}</span></a
          >`)}
      </nav>
      <div class="fb-content">${n}</div>
      ${a?v`<div class="fb-fab">${r}</div>`:b}
    </div>
  `},Fn=(e,t)=>t.length?v`<ha-alert alert-type="warning" title="No display is loaded">
        ${Z(t.length,`display`)} could not be set up. Open the integration page to see why.
        <ha-button
          slot="action"
          appearance="plain"
          @click=${()=>H(`/config/integrations/integration/shellyelevateintegration`)}
          >Open</ha-button
        >
      </ha-alert>`:v`<ha-alert alert-type="info" title="No display yet">
        Install Shelly Elevate on a Shelly Wall Display to manage it here.
        <ha-button slot="action" appearance="plain" @click=${()=>Y(e,`install`)}>Install</ha-button>
      </ha-alert>`,In=e=>v`<ha-combo-box-item type="button" compact>
  ${e.icon_path?v`<ha-svg-icon slot="start" .path=${e.icon_path}></ha-svg-icon>`:b}
  <span slot="headline">${e.primary}</span>
  ${e.secondary?v`<span slot="supporting-text">${e.secondary}</span>`:b}
</ha-combo-box-item>`,Ln=new WeakMap,Rn=e=>{let t=Ln.get(e);if(!t){let n=e.filter(A).map(e=>({id:e.entry_id,primary:e.name,secondary:e.available?void 0:`Offline`,icon_path:D}));t=()=>n,Ln.set(e,t)}return t},zn=(e,t,n,r)=>{let i=t.filter(A),a=i.find(e=>e.entry_id===n),o=e=>v`<ha-button
    slot=${e?`field`:`trigger`}
    appearance="filled"
    .disabled=${!i.length}
    @click=${e}
  >
    <ha-svg-icon slot="start" .path=${D}></ha-svg-icon>
    ${a?.name??`Display`}
    <ha-svg-icon slot="end" .path=${Je}></ha-svg-icon>
  </ha-button>`;return N(`ha-generic-picker`)?v`<ha-generic-picker
      class="display-picker"
      .hass=${e}
      .getItems=${Rn(t)}
      .value=${n}
      .rowRenderer=${In}
      label="Display"
      search-label="Search displays"
      @value-changed=${e=>{e.stopPropagation(),e.detail?.value&&r(e.detail.value)}}
    >
      ${o(e=>{e.stopPropagation(),e.currentTarget.parentElement.open()})}
    </ha-generic-picker>`:v`<ha-dropdown
    class="display-picker"
    placement="bottom-end"
    @wa-select=${e=>{e.stopPropagation(),r(e.detail.item.value)}}
  >
    ${o()}
    ${i.map(e=>v`<ha-dropdown-item value=${e.entry_id} .selected=${e.entry_id===n}>
        <ha-svg-icon slot="icon" .path=${D}></ha-svg-icon>
        ${e.name}${e.available?b:v` (offline)`}
      </ha-dropdown-item>`)}
  </ha-dropdown>`},Bn=o`
  :host {
    display: block;
    height: 100%;
  }
  /* The menu button of a main page keeps the 24px gap hass-tabs-subpage puts after it; on stock
     pages (hass-subpage / ha-top-app-bar-fixed, and back-arrow tab pages) the title starts 8px
     after the 48px button, so pull it back by 16px. */
  hass-tabs-subpage {
    --main-title-margin: calc(var(--ha-space-2) - var(--ha-space-6));
  }
  .header {
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  /* the display picker button (ha-config-logs) */
  .display-picker {
    --md-list-item-leading-icon-color: var(--ha-color-primary-50);
    --mdc-icon-size: var(--ha-space-6);
    flex-shrink: 0;
    min-width: 0;
    max-width: 50%;
  }
  .display-picker ha-button {
    max-width: 100%;
  }
  .display-picker ha-button::part(label) {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  :host([narrow]) .display-picker ha-svg-icon[slot="start"] {
    display: none;
  }
  /* search bar below the app bar (ha-config-logs); the display picker sits at its end */
  .search {
    position: sticky;
    top: 0;
    z-index: 2;
    display: flex;
    align-items: center;
    background: var(--sidebar-background-color);
    border-bottom: 1px solid var(--divider-color);
  }
  .search ha-input-search,
  .search ha-input {
    flex: 1;
    min-width: 0;
    padding: var(--ha-space-3);
  }
  .search .display-picker {
    margin-inline-end: var(--ha-space-3);
  }

  .fb-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--primary-background-color);
  }
  .fb-toolbar {
    display: flex;
    align-items: center;
    gap: var(--ha-space-2);
    height: calc(var(--header-height, 56px) + var(--safe-area-inset-top, 0px));
    padding: var(--safe-area-inset-top, 0px) 12px 0;
    background: var(--sidebar-background-color);
    color: var(--sidebar-text-color);
    border-bottom: 1px solid var(--divider-color);
    font-size: var(--ha-font-size-xl);
  }
  .fb-title {
    flex: 1;
    margin-inline-start: var(--ha-space-4);
  }
  .fb-tabs {
    display: flex;
    overflow-x: auto;
    background: var(--sidebar-background-color);
    border-bottom: 1px solid var(--divider-color);
  }
  .fb-tabs a {
    display: inline-flex;
    align-items: center;
    gap: var(--ha-space-2);
    padding: 0 var(--ha-space-4);
    height: 48px;
    color: var(--sidebar-text-color);
    text-decoration: none;
    border-bottom: 2px solid transparent;
    white-space: nowrap;
  }
  .fb-tabs a.active {
    color: var(--primary-color);
    border-bottom-color: var(--primary-color);
  }
  .fb-content {
    flex: 1;
    overflow: auto;
  }
  .fb-fab {
    position: fixed;
    right: calc(16px + var(--safe-area-inset-right, 0px));
    bottom: calc(16px + var(--safe-area-inset-bottom, 0px));
    display: flex;
    gap: var(--ha-space-2);
    z-index: 1;
  }
`,Vn=class extends w{constructor(){super(),this.diff=[],this.selectable=!1,this.selected=new Set,this.emptyText=`No changes – already up to date.`}_toggle(e,t){let n=new Set(this.selected);t?n.add(e):n.delete(e),this._emit(n)}_emit(e){this.selected=e,this.dispatchEvent(new CustomEvent(`selection-changed`,{detail:{selected:e}}))}_renderSelectAll(){let e=this.diff.every(e=>this.selected.has(e.key));return v`<ha-list-item-base>
      <ha-checkbox
        slot="start"
        .checked=${e}
        .indeterminate=${!e&&this.selected.size>0}
        @change=${e=>this._emit(z(e)?new Set(this.diff.map(e=>e.key)):new Set)}
      ></ha-checkbox>
      <span slot="headline">Select all</span>
      <span slot="end" class="secondary">${this.selected.size} of ${this.diff.length}</span>
    </ha-list-item-base>`}render(){return this.diff.length?v`
      <ha-list-base class="rows" aria-label="Changes">
        ${this.selectable?this._renderSelectAll():b}
        ${this.diff.map(e=>v`
            <ha-list-item-base>
              ${this.selectable?v`<ha-checkbox
                    slot="start"
                    .checked=${this.selected.has(e.key)}
                    @change=${t=>this._toggle(e.key,z(t))}
                  ></ha-checkbox>`:b}
              <span slot="headline">${e.key}</span>
              <span slot="supporting-text">${an(e.current)} → ${an(e.new)}</span>
            </ha-list-item-base>
          `)}
      </ha-list-base>
    `:v`<p>${this.emptyText}</p>`}};k(Vn,`properties`,{diff:{attribute:!1},selectable:{type:Boolean},selected:{attribute:!1},emptyText:{attribute:`empty-text`}}),k(Vn,`styles`,[U,o`
      :host {
        display: block;
      }
      p {
        margin: var(--ha-space-2) 0;
      }
    `]),G(`sep-diff-table`,Vn);var Hn=e=>Array.isArray(e)&&e.length>0,Un=class extends w{constructor(){super(),k(this,`_closed`,B(()=>this._open=!1)),this.devices=[],this.profiles=[],this._open=!1,this._stage=`select`,this._data={profile:``,displays:[]},this._preview={},this._busy=!1,this._error=``}show(e,t){let n=this.profiles.find(e=>e.default)?.id??this.profiles[0]?.id??``;this._data={profile:e??n,displays:t??[]},this._stage=`select`,this._preview={},this._error=``,this._busy=!1,this._open=!0}_close(){this._stage!==`applying`&&(this._open=!1)}get _profileName(){return this.profiles.find(e=>e.id===this._data.profile)?.name??``}async _previewChanges(){this._busy=!0,this._error=``;try{let{results:e,errors:t}=await this.api.profilesApply(this._data.profile,this._data.displays,!0),n={};for(let r of this._data.displays)n[r]=r in t?{error:t[r]}:e[r]??[];this._preview=n,this._stage=`preview`}catch(e){this._error=M(e)}finally{this._busy=!1}}async _apply(){let e=Object.entries(this._preview).filter(([,e])=>Hn(e)).map(([e])=>e);if(e.length){this._stage=`applying`,this._error=``;try{let{results:t,errors:n}=await this.api.profilesApply(this._data.profile,e,!1),r=e.filter(e=>e in t&&!(e in n)),i=e.filter(e=>e in n||!(e in t));if(!r.length){this._error=i.map(e=>`${j(this.devices,e)}: ${n[e]??`failed`}`).join(`
`),this._stage=`preview`;return}let a=r.reduce((e,n)=>e+(t[n]?.length??0),0),o=`Profile “${this._profileName}”`;i.length?q(this,`${o} applied to ${r.length} of ${Z(e.length,`display`)}`,`warning`,i.map(e=>`${j(this.devices,e)}: ${n[e]??`failed`}`)):q(this,`${o} applied to ${Z(r.length,`display`)} (${Z(a,`setting`)} changed)`,`success`),this._open=!1,this.dispatchEvent(new CustomEvent(`applied`))}catch(e){this._error=M(e),this._stage=`preview`}}}_renderSelect(){let e=this.devices.filter(A),t=[{name:`profile`,required:!0,selector:{select:{mode:`dropdown`,options:this.profiles.map(e=>({value:e.id,label:`${e.name}${e.default?` (default)`:``}`}))}}},{name:`displays`,selector:{select:{multiple:!0,mode:`list`,options:e.map(e=>({value:e.entry_id,label:`${e.name}${e.available?``:` (offline)`}`}))}}}];return v`
      <ha-form
        .hass=${this.api.hass}
        .data=${this._data}
        .schema=${t}
        .computeLabel=${e=>e.name===`profile`?`Profile`:`Displays`}
        @value-changed=${e=>{e.stopPropagation(),this._data={profile:e.detail.value.profile??``,displays:e.detail.value.displays??[]}}}
      ></ha-form>
      ${e.length?b:v`<ha-alert alert-type="info">No displays are set up.</ha-alert>`}
      <p class="secondary note">
        Per-display settings (IDs, names) are never applied. A backup of each display is taken before it is changed.
      </p>
    `}_renderPreview(){let e=Object.entries(this._preview),t=e.filter(([,e])=>Hn(e)).length,n=e.reduce((e,[,t])=>e+(Array.isArray(t)?t.length:0),0);return v`
      <ha-alert alert-type=${t?`info`:`success`}>
        ${t?v`Applying <b>${this._profileName}</b> changes ${Z(n,`setting`)} on ${Z(t,`display`)}.`:v`All selected displays already match <b>${this._profileName}</b>.`}
      </ha-alert>
      <div class="panels">
        ${e.map(([e,t])=>{let n=!Array.isArray(t),r=n?`Error`:t.length?Z(t.length,`change`):`Up to date`;return v`
            <ha-expansion-panel
              outlined
              .header=${j(this.devices,e)}
              .secondary=${r}
              .expanded=${n||t.length>0}
            >
              ${n?v`<ha-alert alert-type="error">${t.error}</ha-alert>`:v`<sep-diff-table .diff=${t}></sep-diff-table>`}
            </ha-expansion-panel>
          `})}
      </div>
    `}_renderFooter(){if(this._stage===`select`)return v`
        <ha-button slot="secondaryAction" appearance="plain" @click=${this._close}>Cancel</ha-button>
        <ha-button
          slot="primaryAction"
          .loading=${this._busy}
          ?disabled=${!this._data.profile||!this._data.displays.length||this._busy}
          @click=${this._previewChanges}
          >Preview changes</ha-button
        >
      `;let e=this._stage===`applying`;return v`
      <ha-button slot="secondaryAction" appearance="plain" ?disabled=${e} @click=${()=>this._stage=`select`}
        >Back</ha-button
      >
      <ha-button slot="primaryAction" .loading=${e} ?disabled=${!Object.values(this._preview).some(Hn)||e} @click=${this._apply}
        >Apply to displays</ha-button
      >
    `}render(){return v`
      <ha-dialog
        .open=${this._open}
        width="large"
        header-title="Apply profile"
        .headerSubtitle=${this._stage===`select`?void 0:this._profileName}
        .preventScrimClose=${this._stage===`applying`||this._busy}
        @closed=${this._closed}
      >
        ${this._error?v`<ha-alert alert-type="error" class="error-alert" title="Could not apply the profile"
              ><span class="pre">${this._error}</span></ha-alert
            >`:b}
        ${this._stage===`select`?this._renderSelect():this._renderPreview()}
        <ha-dialog-footer slot="footer">${this._renderFooter()}</ha-dialog-footer>
      </ha-dialog>
    `}};k(Un,`properties`,{api:{attribute:!1},devices:{attribute:!1},profiles:{attribute:!1},_open:{state:!0},_stage:{state:!0},_data:{state:!0},_preview:{state:!0},_busy:{state:!0},_error:{state:!0}}),k(Un,`styles`,[U,W,o`
      .note {
        margin-top: var(--ha-space-4);
        font-size: var(--ha-font-size-s);
      }
      .error-alert {
        margin-bottom: var(--ha-space-4);
      }
      .pre {
        white-space: pre-line;
      }
      .panels {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-2);
        margin-top: var(--ha-space-4);
      }
      ha-expansion-panel {
        --expansion-panel-content-padding: 0 var(--ha-space-4);
      }
    `]),G(`sep-apply-profile-dialog`,Un);var Wn=[{action:`screen.wake`,label:`Wake`,icon:St},{action:`screen.sleep`,label:`Sleep`,icon:ht},{action:`webview.reload`,label:`Reload dashboard`,icon:xt},{action:`app.restart`,label:`Restart app`,icon:We,destructive:!0,confirm:`The Shelly Elevate app restarts; the screen is blank for a few seconds.`},{action:`device.reboot`,label:`Reboot`,icon:pt,destructive:!0,confirm:`The displays reboot and are offline for about a minute.`}],Gn={not_loaded:`Not loaded`,setup_error:`Failed to set up`,setup_retry:`Failed setup, will retry`,migration_error:`Migration error`,failed_unload:`Failed to unload`,setup_in_progress:`Initializing`,unload_in_progress:`Unloading`},Kn=[{value:`online`,label:`Online`},{value:`offline`,label:`Offline`},{value:`not_loaded`,label:`Not loaded`}],qn=e=>A(e)?e.available?`online`:`offline`:`not_loaded`,Jn=e=>A(e)?e.available?`Online`:`Offline`:Gn[e.state??``]??`Not loaded`,Yn=class extends w{constructor(){super(),k(this,`_iconRequested`,!1),this.devices=[],this.loading=!1,this.error=``,this.narrow=!1,this._selected=[],this._busy=``,this._profiles=[],this._icon=``,this._statusFilter=[],this._filterExpanded=!0,this._hasFilter=N(`ha-filter-states`),this._hasFilter||Bt().then(e=>this._hasFilter=e)}willUpdate(e){if(this.page&&!this._iconRequested&&(this._iconRequested=!0,Ut(this.page.hass,`shellyelevateintegration`).then(e=>this._icon=e)),e.has(`devices`)){let e=new Set(this.devices.filter(A).map(e=>e.entry_id)),t=this._selected.filter(t=>e.has(t));t.length!==this._selected.length&&(this._selected=t)}}async _run(e){let t=[...this._selected];if(t.length&&!((e.destructive||t.length>1)&&!await K(this,{title:`${e.label} ${Z(t.length,`display`)}?`,text:e.confirm,items:t.map(e=>j(this.devices,e)),confirmText:e.label,destructive:e.destructive}))){this._busy=e.action;try{let n=await this.api.command(t,e.action),r=Object.entries(n).filter(([,e])=>!e.ok);r.length?q(this,`${e.label}: ${t.length-r.length} succeeded, ${r.length} failed`,r.length===t.length?`error`:`warning`,r.map(([e,t])=>`${j(this.devices,e)}: ${t.error??`failed`}`)):q(this,`${e.label}: sent to ${Z(t.length,`display`)}`,`success`)}catch(t){J(this,`${e.label} failed`,t)}finally{this._busy=``}}}async _applyProfile(){this._busy=`profile`;try{this._profiles=(await this.api.profilesList()).profiles}catch(e){J(this,`Could not load profiles`,e);return}finally{this._busy=``}if(!this._profiles.length){q(this,`There are no profiles yet. Create one in the Profiles tab.`,`warning`);return}await this.updateComplete,this.renderRoot.querySelector(`sep-apply-profile-dialog`)?.show(void 0,[...this._selected])}_onBulkSelect(e){let t=e.detail.item.value,n=Wn.find(e=>e.action===t);n?this._run(n):t===`profile`&&this._applyProfile()}_onRowMenu(e,t){let n=t.detail.item.value;n===`device`&&e.device_id?H(`/config/devices/device/${e.device_id}`):n===`settings`||n===`backups`?Y(this,n,e.entry_id):n===`revert`&&e.host&&Yt(this,{host:e.host,entryId:e.entry_id,name:e.name})}_status(e){let t=Jn(e),n=A(e)&&!e.available?`color:var(--error-color)`:``,r=[e.legacy?v`<ha-label dense description="Pre-v1 app with the legacy HTTP API">Legacy</ha-label>`:b,e.adb?v`<ha-label dense description="ADB access available (updates, rescue)">ADB</ha-label>`:b];return!e.legacy&&!e.adb?v`<span style=${n}>${t}</span>`:v`<div style="display:flex;flex-wrap:wrap;align-items:center;gap:4px">
      <span style=${n}>${t}</span>${r}
    </div>`}_rowMenu(e){let t=A(e);return v`
      <ha-dropdown placement="bottom-end" @click=${Q} @wa-select=${t=>this._onRowMenu(e,t)}>
        <ha-icon-button slot="trigger" .label=${`Actions`} .path=${T}></ha-icon-button>
        <ha-dropdown-item value="settings" .disabled=${!t}>
          <ha-svg-icon slot="icon" .path=${yt}></ha-svg-icon>
          Settings
        </ha-dropdown-item>
        <ha-dropdown-item value="backups" .disabled=${!t}>
          <ha-svg-icon slot="icon" .path=${Ge}></ha-svg-icon>
          Backups
        </ha-dropdown-item>
        <ha-dropdown-item value="device" .disabled=${!e.device_id}>
          <ha-svg-icon slot="icon" .path=${st}></ha-svg-icon>
          Device page
        </ha-dropdown-item>
        <wa-divider></wa-divider>
        <ha-dropdown-item value="revert" variant="danger" .disabled=${!e.host}>
          <ha-svg-icon slot="icon" .path=${ct}></ha-svg-icon>
          Revert to stock…
        </ha-dropdown-item>
      </ha-dropdown>
    `}_columns(){return{icon:{title:``,type:`icon`,showNarrow:!0,template:()=>this._icon?v`<img alt="" crossorigin="anonymous" referrerpolicy="no-referrer" src=${this._icon} />`:v`<ha-svg-icon .path=${D}></ha-svg-icon>`},name:{title:`Name`,main:!0,sortable:!0,filterable:!0,direction:`asc`,grows:!0,flex:2,minWidth:`150px`},model:{title:`Model`,sortable:!0,filterable:!0,groupable:!0,minWidth:`120px`},firmware:{title:`Firmware version`,sortable:!0,filterable:!0,minWidth:`120px`},host:{title:`IP address`,sortable:!0,filterable:!0,minWidth:`120px`},status:{title:`Status`,sortable:!0,groupable:!0,showNarrow:!0,minWidth:`120px`,template:e=>this._status(e.device)},actions:{title:``,type:`overflow-menu`,showNarrow:!0,template:e=>this._rowMenu(e.device)}}}_rows(){let e=this._statusFilter;return(e.length?this.devices.filter(t=>e.includes(qn(t))):this.devices).map(e=>({entry_id:e.entry_id,name:e.name,model:A(e)?e.model??`Wall Display`:`—`,firmware:e.fw_version??`—`,host:e.host??`—`,status:Jn(e),selectable:A(e),device:e}))}_selectionBar(){let e=!!this._busy,t=t=>v`<ha-assist-chip slot="trigger" .label=${t} ?disabled=${e}>
      <ha-svg-icon slot="trailing-icon" .path=${at}></ha-svg-icon>
    </ha-assist-chip>`,n=Wn.map(e=>v`<ha-dropdown-item value=${e.action} variant=${e.destructive?`danger`:`default`}>
        <ha-svg-icon slot="icon" .path=${e.icon}></ha-svg-icon>${e.label}
      </ha-dropdown-item>`),r=v`<ha-dropdown-item value="profile">
      <ha-svg-icon slot="icon" .path=${Qe}></ha-svg-icon>Apply profile…
    </ha-dropdown-item>`;return this.narrow?v`<ha-dropdown slot="selection-bar" @wa-select=${this._onBulkSelect}>
        ${t(`Actions`)} ${n}
        <wa-divider></wa-divider>
        ${r}
      </ha-dropdown>`:v`
      <ha-dropdown slot="selection-bar" @wa-select=${this._onBulkSelect}>${t(`Send command`)} ${n}</ha-dropdown>
      <ha-dropdown slot="selection-bar" @wa-select=${this._onBulkSelect}>
        <ha-icon-button slot="trigger" .label=${`More actions`} .path=${T} ?disabled=${e}></ha-icon-button>
        ${r}
      </ha-dropdown>
    `}_filterPane(){return this._hasFilter?v`<ha-filter-states
      slot="filter-pane"
      label="Status"
      .states=${Kn}
      .value=${this._statusFilter}
      .narrow=${this.narrow}
      .expanded=${this._filterExpanded}
      @expanded-changed=${e=>this._filterExpanded=e.detail.expanded}
      @data-table-filter-changed=${e=>this._statusFilter=e.detail.value??[]}
    ></ha-filter-states>`:b}_fab(){return v`<ha-button slot="fab" size="l" @click=${()=>Y(this,`install`)}>
      <ha-svg-icon slot="start" .path=${dt}></ha-svg-icon>Add display
    </ha-button>`}_empty(){return v`<div class="empty" slot="empty">
      <ha-svg-icon .path=${D}></ha-svg-icon>
      <h1>Start managing your displays</h1>
      <p>Install Shelly Elevate on a Shelly Wall Display. It then shows up here.</p>
      <ha-button appearance="plain" size="s" @click=${()=>Y(this,`install`)}>Install a display</ha-button>
    </div>`}_renderFallback(){let e=this.devices.filter(A),t=e.length>0&&e.every(e=>this._selected.includes(e.entry_id)),n=v`
      <div class="content">
        ${this.error?v`<ha-alert alert-type="error">${this.error}</ha-alert>`:b}
        <ha-card>
          <h1 class="card-header">Displays</h1>
          <div class="header-actions">
            <ha-checkbox
              .checked=${t}
              .indeterminate=${!t&&this._selected.length>0}
              ?disabled=${!e.length}
              @change=${t=>this._selected=z(t)?e.map(e=>e.entry_id):[]}
              >All</ha-checkbox
            >
          </div>
          ${this.devices.length?v`<ha-list-base>
                ${this.devices.map(e=>v`<ha-list-item-base>
                    <ha-checkbox
                      slot="start"
                      ?disabled=${!A(e)}
                      .checked=${this._selected.includes(e.entry_id)}
                      @change=${t=>{this._selected=z(t)?[...this._selected,e.entry_id]:this._selected.filter(t=>t!==e.entry_id)}}
                    ></ha-checkbox>
                    <span slot="headline">${e.name}</span>
                    <span slot="supporting-text">${e.model??``} · ${e.fw_version??`–`} · ${e.host??`–`}</span>
                    <span slot="end" style="display:flex;align-items:center">${this._status(e)}${this._rowMenu(e)}</span>
                  </ha-list-item-base>`)}
              </ha-list-base>`:this._empty()}
          ${this._selected.length?v`<div class="card-actions">${this._selectionBar()}</div>`:b}
        </ha-card>
      </div>
    `;return Pn(this,this.page,n,this._fab())}render(){if(!this.page)return b;let e=v`<sep-apply-profile-dialog
      .api=${this.api}
      .devices=${this.devices}
      .profiles=${this._profiles}
    ></sep-apply-profile-dialog>`;return N(`hass-tabs-subpage-data-table`)?v`
      <hass-tabs-subpage-data-table
        class=${this.narrow?`narrow`:``}
        main-page
        has-fab
        clickable
        selectable
        id="entry_id"
        .hass=${this.page.hass}
        .narrow=${this.narrow}
        .route=${this.page.route}
        .tabs=${this.page.tabs}
        .columns=${this._columns()}
        .data=${this._rows()}
        .loading=${this.loading&&!this.devices.length}
        .loadError=${this.error||void 0}
        .empty=${!this.devices.length&&!this.loading&&!this.error}
        .selected=${this._selected.length}
        .noDataText=${`No displays`}
        .searchLabel=${`Search ${Z(this.devices.length,`display`)}`}
        .initialSorting=${{column:`name`,direction:`asc`}}
        @selection-changed=${e=>{Array.isArray(e.detail?.value)&&(this._selected=e.detail.value)}}
        ?has-filters=${this._hasFilter}
        .filters=${+!!this._statusFilter.length}
        @clear-filter=${()=>this._statusFilter=[]}
        @row-click=${e=>{let t=this.devices.find(t=>t.entry_id===e.detail.id);t&&(A(t)?Y(this,`settings`,t.entry_id):H(`/config/integrations/integration/shellyelevateintegration`))}}
      >
        ${Nn(this)} ${this._filterPane()} ${this._selectionBar()} ${this.devices.length?b:this._empty()}
        ${this._fab()}
      </hass-tabs-subpage-data-table>
      ${e}
    `:v`${this._renderFallback()}${e}`}};k(Yn,`properties`,{page:{attribute:!1},api:{attribute:!1},devices:{attribute:!1},loading:{type:Boolean},error:{},narrow:{type:Boolean,reflect:!0},_selected:{state:!0},_busy:{state:!0},_profiles:{state:!0},_icon:{state:!0},_statusFilter:{state:!0},_filterExpanded:{state:!0},_hasFilter:{state:!0}}),k(Yn,`styles`,[U,Bn,o`
      /* as ha-config-devices-dashboard / ha-automation-picker */
      hass-tabs-subpage-data-table {
        --data-table-row-height: 60px;
      }
      hass-tabs-subpage-data-table.narrow {
        --data-table-row-height: 72px;
      }
      .empty {
        --mdc-icon-size: 80px;
        max-width: 500px;
      }
      .empty ha-button {
        --mdc-icon-size: 24px;
      }
      .empty h1 {
        font-size: var(--ha-font-size-3xl);
      }
      ha-assist-chip {
        --ha-assist-chip-container-shape: 10px;
      }
      ha-dropdown ha-assist-chip {
        --md-assist-chip-trailing-space: 8px;
      }
    `]),G(`sep-displays-tab`,Yn);var Xn={adb_connect:`Connect over ADB`,root_check:`Check for root`,dev_settings:`Enable developer settings`,adb_enabled:`Enable ADB debugging`,adb_wifi:`Enable ADB over Wi‑Fi`,adb_tcp:`Keep ADB on port 5555 after reboot`,adb_key:`Trust Home Assistant's ADB key`,download:`Download the Shelly Elevate app`,push:`Copy the app to the display`,install:`Install the app`,cleanup:`Clean up`,perm_audio:`Grant microphone permission`,perm_location:`Grant location permission`,location_on:`Turn on location`,perm_bt_scan:`Grant Bluetooth scan permission`,perm_bt_connect:`Grant Bluetooth connect permission`,write_settings:`Allow changing system settings`,overlay:`Allow drawing over other apps`,usage_stats:`Allow reading the app in front`,doze_whitelist:`Exclude from battery optimisation`,secure_settings:`Let the app switch ADB over Wi‑Fi`,disable_stock:`Keep the stock Shelly app in the background`,stop:`Stop the app`,start:`Start the app`,wait_app:`Wait for the app to start`,provision:`Pair with Home Assistant`,config_entry:`Add the display to Home Assistant`},Zn=new Set([`root_check`,`dev_settings`,`adb_enabled`,`adb_wifi`,`adb_tcp`,`adb_key`,`perm_audio`,`perm_location`,`location_on`,`perm_bt_scan`,`perm_bt_connect`,`write_settings`,`overlay`,`usage_stats`,`doze_whitelist`,`secure_settings`,`disable_stock`,`stop`,`start`]),Qn=new Set([`perm_bt_scan`,`perm_bt_connect`]),$n=new Set([`perm_location`,`location_on`]),er=31,tr=[`wait_app`,`provision`,`config_entry`],nr=[`F`,`H`,`F`,`F`,`H`,`F`,`H`,`H`],rr=`ADB has to be enabled once on the display. Home Assistant then installs and sets up everything over the network.

1. Connect the display to Wi‑Fi in the Shelly settings under **Network**.
2. Update the display to the newest Shelly firmware.
3. In the Shelly settings, open **General → About device** and tap **Firmware** (F) and **Hardware** (H) in this order: **${nr.join(` `)}**
4. In the Android **Developer options**, enable only **ADB debugging** and **ADB over Wi‑Fi** (port 5555). On newer Shelly firmware, also turn on **ADB - WiFi** in the Shelly developer settings (it shows the display's address with port 5555). Note the IP address of the display.
5. Enter the IP address below.`,ir=new Set([`done`,`failed`,`warning`,`skipped`]),ar=`__none__`,or=/^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?!$)|$)){4}$|^[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?$/,sr=e=>{let t=[`adb_connect`,`root_check`,`dev_settings`,`adb_enabled`,`adb_wifi`,`adb_tcp`];return e.install_app&&t.push(`download`,`push`,`install`,`cleanup`),t.push(`perm_audio`,`perm_location`,`location_on`,`perm_bt_scan`,`perm_bt_connect`,`write_settings`,`overlay`,`usage_stats`,`doze_whitelist`,`secure_settings`),e.disable_stock&&t.push(`disable_stock`),t.push(`start`,...tr),t.map(e=>({id:e,label:Xn[e]??e,status:`pending`}))},cr=e=>e>1048576?`${(e/1024/1024).toFixed(1)} MB`:`${Math.round(e/1024)} kB`,lr=(e,t)=>{if(e.error)return String(e.error);switch(`${e.step}:${e.status}`){case`root_check:done`:return[e.root===!1?`Not rooted`:e.root===!0?`Rooted`:``,Zt(e.sdk)].filter(Boolean).join(` · `)||t;case`download:running`:return e.version?`Version ${e.version}`:t;case`download:done`:return e.bytes?`${t?`${t} · `:``}${cr(e.bytes)}`:t;case`push:running`:return e.bytes?cr(e.bytes):t;case`wait_app:done`:return`${e.legacy?`Legacy app`:`App`}${e.version?` ${e.version}`:``} is running`;case`config_entry:done`:return e.updated?`Already configured – existing entry updated`:t;default:return t}},ur={install_app:[`Install the Shelly Elevate app`,`Downloads the version chosen below from GitHub and installs it.`],release:[`App version`,`Latest installs the newest release of the channel. Pick a version to install exactly that one.`],disable_stock:[`Keep the stock Shelly app in the background`,`Keeps the stock Shelly app from covering Shelly Elevate. On Android 11 models (Wall Display XL, X2i and X1i) it stays the home app and is only kept from drawing on top and stopped. On older models it is disabled where Android allows it, which leaves the display without a home app, and otherwise kept from drawing on top.`],profile_id:[`Settings profile`,`Applied to the display after pairing.`],dashboard_url:[`Dashboard URL`,`The page the display shows, e.g. http://homeassistant.local:8123/lovelace/0`]},dr=`v:`,fr=class extends w{constructor(){super(),k(this,`_unsub`,null),k(this,`_cancelled`,!1),k(this,`_updated`,!1),this.devices=[],this.active=!1,this.narrow=!1,this._info=null,this._infoError=``,this._stage=`adb`,this._host=``,this._opts={install_app:!0,channel:`stable`,version:null,disable_stock:!1,profile_id:null,dashboard_url:null},this._provState=`idle`,this._provSteps=[],this._provError=``,this._provResult=null,this._log=[],this._logOpen=!1,this._stepsOpen=!1,this._hasProgressBar=N(`ha-progress-bar`)}willUpdate(e){e.has(`active`)&&this.active&&this.api&&!this._busy&&this._loadInfo(),e.has(`page`)&&this.page&&!this._hasProgressBar&&zt(this.page.hass,this.renderRoot).then(e=>this._hasProgressBar=e)}disconnectedCallback(){super.disconnectedCallback(),this._stopSubscription()}get _busy(){return this._provState===`running`}get _hostValid(){return or.test(this._host)}async _loadInfo(){let e=this._info===null;try{let t=await this.api.installerInfo();this._info=t,this._infoError=``,e?this._opts={...this._opts,profile_id:t.default_profile??null,dashboard_url:t.dashboard_url??null}:this._opts.profile_id&&!t.profiles.some(e=>e.id===this._opts.profile_id)&&(this._opts={...this._opts,profile_id:t.default_profile??null})}catch(e){this._infoError=M(e)}}async _stopSubscription(){let e=this._unsub;if(this._unsub=null,e)try{await e()}catch{}}_back(){this._stage=`adb`,this._resetProvision()}async _askCancel(){await K(this,{title:`Cancel the installation?`,text:`The running step is stopped. The display may be left half-configured; you can run the installation again.`,confirmText:`Cancel installation`,dismissText:`Keep installing`,destructive:!0})&&this._busy&&await this._cancel()}async _cancel(){await this._stopSubscription(),this._provState===`running`&&(this._addLog({kind:`error`,text:`Cancelled`}),this._provState=`error`,this._provError=``,this._cancelled=!0),this._failRunning(`Cancelled`)}_resetProvision(){this._cancelled=!1,this._updated=!1,this._provState=`idle`,this._provSteps=[],this._provError=``,this._provResult=null,this._log=[],this._stepsOpen=!1}_restart(){this._stage=`adb`,this._host=``,this._resetProvision(),this._loadInfo()}_revert(){Yt(this,{prefill:this._hostValid?this._host.trim():``})}_revertHost(){Yt(this,{host:this._host.trim()})}_continue(){this._hostValid&&(this._stage=`provision`)}_failRunning(e){this._provSteps.some(e=>e.status===`running`)&&(this._provSteps=this._provSteps.map(t=>t.status===`running`?{...t,status:`failed`,detail:t.detail||e}:t))}_stepIndex(e,t){let n=e.findIndex(e=>e.id===t);if(n>=0)return n;let r=t===`adb_key`?e.findIndex(e=>e.id===`adb_tcp`):-1,i=r>=0?r+1:e.findIndex(e=>e.id===tr[0]),a={id:t,label:Xn[t]??t,status:`pending`};return i>=0&&!tr.includes(t)?(e.splice(i,0,a),i):(e.push(a),e.length-1)}_addLog(...e){this._log=[...this._log,...e]}_logStep(e,t){if(e.status===`running`)this._addLog(e.command?hn(e.command):{kind:`info`,text:`# ${t}`});else if(e.status===`failed`)this._addLog({kind:Zn.has(e.step)?`warning`:`error`,text:String(e.error??`failed`)});else if(e.status===`done`){let t=e.output?.replace(/\r/g,``).trimEnd();t?this._addLog(...t.split(`
`).map(e=>({kind:`output`,text:e}))):e.step===`download`&&e.bytes&&this._addLog({kind:`output`,text:`${e.bytes} bytes`})}}_provisionStep(e){e.step===`config_entry`&&e.status===`done`&&(this._updated=!!e.updated);let t=[...this._provSteps];e.step===`root_check`&&e.status===`done`&&`sdk`in e&&!((e.sdk??0)>=er)&&(t=t.filter(e=>!Qn.has(e.id))),e.step===`root_check`&&e.status===`done`&&(e.sdk??0)>=er&&(t=t.filter(e=>!$n.has(e.id)));let n=this._stepIndex(t,e.step),r=t[n];if(this._logStep(e,r.label),t[n]={...r,status:e.status===`failed`&&Zn.has(e.step)?`warning`:e.status,detail:lr(e,r.detail)},e.status===`running`)for(let e=0;e<n;e++)t[e].status===`pending`&&(t[e]={...t[e],status:`skipped`});this._provSteps=t}_provisionEvent(e){switch(e.type){case`step`:this._provisionStep(e);break;case`done`:this._addLog({kind:`info`,text:`# Finished`}),this._provState=`done`,this._provResult=e,this._provSteps=this._provSteps.map(e=>e.status===`pending`?{...e,status:`skipped`}:e),this._provSteps.some(e=>e.status===`warning`)&&(this._stepsOpen=!0),this._stopSubscription(),Jt(this),q(this,`${e.name??`The display`} was ${this._updated?`updated`:`added to Home Assistant`}`,`success`);break;case`error`:this._log.at(-1)?.text!==e.error&&this._addLog({kind:`error`,text:`Error: ${e.error}`}),this._provState=`error`,this._provError=e.error,this._failRunning(e.error),this._stopSubscription()}}async _startProvision(){let e=this._host.trim();if(!or.test(e)){q(this,`Enter the display's IP address`,`warning`);return}this._resetProvision(),this._provState=`running`,this._provSteps=sr(this._opts);try{this._unsub=await this.api.subscribeProvision(e,this._opts,e=>this._provisionEvent(e))}catch(e){this._provState=`error`,this._provError=M(e)}}_logFileName(){let e=new Date().toISOString().slice(0,19).replace(/[:T]/g,`-`);return`shelly-elevate-install-${this._host||`display`}-${e}.txt`}async _copyLog(e){e.stopPropagation(),await Wt(gn(this._log)),q(this,`Copied to clipboard`)}_downloadLog(e){e.stopPropagation(),en(this._logFileName(),`${gn(this._log)}\n`)}_hostInput(e,t){let n=!!this._host&&!this._hostValid;return v`<ha-input
      label="IP address of the display"
      placeholder="192.168.1.50"
      inputmode="decimal"
      autocomplete="off"
      .value=${this._host}
      .invalid=${n}
      .validationMessage=${n?`Enter an IP address or host name`:``}
      ?disabled=${e}
      @input=${e=>this._host=R(e).trim()}
      @keydown=${e=>e.key===`Enter`&&t?.()}
    ></ha-input>`}_renderDescription(e){return N(`ha-markdown`)?v`<ha-markdown .content=${e}></ha-markdown>`:v`<p>${e}</p>`}_renderAdbSteps(){return N(`ha-markdown`)?this._renderDescription(rr):v`
      <p>ADB has to be enabled once on the display. Home Assistant then installs and sets up everything over the network.</p>
      <ol>
        <li>Connect the display to Wi‑Fi in the Shelly settings under <b>Network</b>.</li>
        <li>Update the display to the newest Shelly firmware.</li>
        <li>
          In the Shelly settings, open <b>General → About device</b> and tap <b>Firmware</b> (F) and
          <b>Hardware</b> (H) in this order: <b>${nr.join(` `)}</b>
        </li>
        <li>
          In the Android <b>Developer options</b>, enable only <b>ADB debugging</b> and <b>ADB over Wi‑Fi</b> (port
          5555). On newer Shelly firmware, also turn on <b>ADB - WiFi</b> in the Shelly developer settings (it shows
          the display's address with port 5555). Note the IP address of the display.
        </li>
        <li>Enter the IP address below.</li>
      </ol>
    `}_renderAdbStage(){return v`
      <ha-card>
        <h1 class="card-header">Prepare the display</h1>
        <div class="card-content">
          ${this._renderAdbSteps()} ${this._hostInput(!1,()=>this._continue())}
        </div>
        <div class="card-actions">
          <ha-button appearance="filled" ?disabled=${!this._hostValid} @click=${this._continue}>Next</ha-button>
        </div>
      </ha-card>
      <ha-card>
        <h1 class="card-header">Revert a display to stock</h1>
        <div class="card-content">
          <p>
            Removes Shelly Elevate and everything its installation changed, and gives the display back to the stock Shelly
            app. Also works for displays that are not in Home Assistant.
          </p>
        </div>
        <div class="card-actions">
          <ha-button appearance="plain" @click=${this._revert}>Revert a display…</ha-button>
        </div>
      </ha-card>
    `}_optionsSchema(){let e=this._info?.releases??[],t=t=>{let n=e.find(e=>t||!e.prerelease)?.version;return`Latest ${t?`beta`:`stable`}${n?` (${n})`:``}`},n={name:`release`,required:!0,selector:{select:{mode:`dropdown`,options:[{value:`stable`,label:t(!1)},{value:`beta`,label:t(!0)},...e.map(e=>({value:`${dr}${e.version}`,label:[e.version,e.prerelease?`beta`:``,e.published?new Date(e.published).toLocaleDateString(this.page.hass.locale?.language):``].filter(Boolean).join(` · `)}))]}}};return[{name:`install_app`,selector:{boolean:{}}},...this._opts.install_app?[n]:[],{name:`disable_stock`,selector:{boolean:{}}},{name:`profile_id`,required:!0,selector:{select:{mode:`dropdown`,options:[{value:ar,label:`No profile`},...(this._info?.profiles??[]).map(e=>({value:e.id,label:`${e.name}${e.default?` (default)`:``}`}))]}}},{name:`dashboard_url`,selector:{text:{type:`url`}}}]}_renderOptions(e){let{channel:t,version:n,...r}=this._opts,i={...r,release:n?`${dr}${n}`:t,profile_id:this._opts.profile_id||ar,dashboard_url:this._opts.dashboard_url??``};return v`<ha-form
      .hass=${this.page.hass}
      .data=${i}
      .schema=${this._optionsSchema()}
      .disabled=${e}
      .computeLabel=${e=>ur[e.name]?.[0]??e.name}
      .computeHelper=${e=>ur[e.name]?.[1]}
      @value-changed=${e=>{e.stopPropagation();let t=e.detail.value,n=t.release??`stable`;this._opts={install_app:!!t.install_app,channel:n===`beta`?`beta`:`stable`,version:n.startsWith(dr)?n.slice(2):null,disable_stock:!!t.disable_stock,profile_id:t.profile_id&&t.profile_id!==ar?t.profile_id:null,dashboard_url:t.dashboard_url||null}}}
    ></ha-form>`}_renderProgressBar(){let e=this._provSteps,t=e.filter(e=>ir.has(e.status)).length,n=e.find(e=>e.status===`running`),r=this._provState,i=r===`done`?100:e.length?Math.round(t/e.length*100):0,a=e.findIndex(e=>e.status===`failed`),o=e.filter(e=>e.status===`warning`).length,s=this._cancelled?`Cancelled`:`Failed`,c;return c=r===`done`?o?`Finished – ${Z(o,`optional step`)} did not work`:`Finished`:r===`error`?a>=0?`${s} at step ${a+1} of ${e.length}: ${e[a].label}`:s:`Step ${Math.min(t+1,e.length)} of ${e.length}: ${n?.label??`Starting…`}`,v`
      ${this._hasProgressBar?v`<ha-progress-bar .value=${i} ?loading=${r===`running`} aria-label="Installation progress"></ha-progress-bar>`:v`<progress max="100" .value=${i}></progress>`}
      <p class="status" role="status">${c}</p>
    `}_renderProgress(){let e=this._provResult,t=this._provState,n=this._provSteps.filter(e=>ir.has(e.status)&&e.status!==`failed`).length;return v`
      <ha-card>
        <h1 class="card-header">Installation on ${this._host}</h1>
        <div class="card-content">
          ${this._renderProgressBar()}
          ${t===`error`&&this._cancelled?v`<ha-alert alert-type="warning" title="Installation cancelled">
                The display may be partly set up. You can run the installation again.
              </ha-alert>`:b}
          ${t===`error`&&!this._cancelled?v`<ha-alert alert-type="error" title="Installation failed">
                ${this._provError}
                ${/revert the display/i.test(this._provError)?v`<ha-button slot="action" appearance="plain" @click=${this._revertHost}>Revert…</ha-button>`:b}
              </ha-alert>`:b}
          ${t===`done`&&e?this._renderSuccess(e):b}
          ${t===`running`?v`<ha-alert alert-type="info">Keep this page open until the installation has finished.</ha-alert>`:b}
          <div class="panels">
            <ha-expansion-panel
              outlined
              .header=${`Steps`}
              .secondary=${`${n} of ${this._provSteps.length} done`}
              .expanded=${this._stepsOpen}
              @expanded-changed=${e=>{e.stopPropagation(),this._stepsOpen=e.detail.expanded}}
            >
              <sep-step-list .steps=${this._provSteps}></sep-step-list>
            </ha-expansion-panel>
            <ha-expansion-panel
              class="log"
              outlined
              .header=${`Log`}
              .secondary=${`${this._log.length} ${this._log.length===1?`line`:`lines`}`}
              .expanded=${this._logOpen}
              @expanded-changed=${e=>{e.stopPropagation(),this._logOpen=e.detail.expanded}}
            >
              <ha-icon-button
                slot="icons"
                .label=${`Copy to clipboard`}
                .path=${$e}
                ?disabled=${!this._log.length}
                @click=${this._copyLog}
                @keydown=${Q}
              ></ha-icon-button>
              <ha-icon-button
                slot="icons"
                .label=${`Download log`}
                .path=${E}
                ?disabled=${!this._log.length}
                @click=${this._downloadLog}
                @keydown=${Q}
              ></ha-icon-button>
              <sep-install-log .lines=${this._log}></sep-install-log>
            </ha-expansion-panel>
          </div>
        </div>
        ${t===`done`?v`<div class="card-actions">
              <ha-button appearance="plain" @click=${this._restart}>Install another display</ha-button>
              ${this._renderOpenDevice(e)}
            </div>`:t===`running`?v`<div class="card-actions">
                <ha-button appearance="plain" variant="danger" @click=${this._askCancel}>Cancel</ha-button>
              </div>`:v`<div class="card-actions split">
                <ha-button appearance="plain" @click=${this._resetProvision}>Back</ha-button>
                <ha-button appearance="filled" @click=${this._startProvision}>Try again</ha-button>
              </div>`}
      </ha-card>
    `}_renderSuccess(e){let t=e.name??`The display`,n=this._provSteps.some(e=>e.status===`warning`);return v`<ha-alert alert-type="success" title="${t} is ready">
      ${this._updated?`${t} was already set up in Home Assistant. Its address and pairing were updated.`:e.legacy?`${t} runs the legacy app and was added to Home Assistant.`:`Shelly Elevate is installed and paired with Home Assistant.`}${n?` Some optional steps did not work; they are marked under Steps.`:``}
    </ha-alert>`}_renderOpenDevice(e){let t=e?.device_id??(e?.entry_id?this.devices.find(t=>t.entry_id===e.entry_id)?.device_id:void 0);if(t){let e=`/config/devices/device/${t}`;return v`<ha-button appearance="filled" @click=${()=>H(e)}>Open device</ha-button>`}return v`<ha-button appearance="filled" @click=${()=>Y(this,`displays`)}>Show displays</ha-button>`}_renderProvisionStage(){return this._provState===`idle`?v`
      <ha-card>
        <h1 class="card-header">Install and pair</h1>
        <div class="card-content">
          ${this._renderDescription(`Home Assistant connects to the display over ADB, installs the app and adds the display.`)}
          ${this._hostInput(!1,()=>this._startProvision())} ${this._renderOptions(!1)}
        </div>
        <div class="card-actions split">
          <ha-button appearance="plain" @click=${this._back}>Back</ha-button>
          <ha-button appearance="filled" ?disabled=${!this._hostValid} @click=${this._startProvision}>Install</ha-button>
        </div>
      </ha-card>
    `:this._renderProgress()}_renderBody(){return this._infoError&&!this._info?v`<ha-alert alert-type="error" title="Could not load the installer">
        ${this._infoError}
        <ha-button slot="action" appearance="plain" @click=${this._loadInfo}>Retry</ha-button>
      </ha-alert>`:this._info?this._stage===`provision`?this._renderProvisionStage():this._renderAdbStage():v`<div class="loading"><ha-spinner></ha-spinner></div>`}render(){return this.page?Pn(this,this.page,v`<div class="content">${this._renderBody()}</div>`):b}};k(fr,`properties`,{page:{attribute:!1},api:{attribute:!1},devices:{attribute:!1},active:{type:Boolean},narrow:{type:Boolean,reflect:!0},_info:{state:!0},_infoError:{state:!0},_stage:{state:!0},_host:{state:!0},_opts:{state:!0},_provState:{state:!0},_provSteps:{state:!0},_provError:{state:!0},_provResult:{state:!0},_log:{state:!0},_logOpen:{state:!0},_stepsOpen:{state:!0},_hasProgressBar:{state:!0}}),k(fr,`styles`,[U,Bn,o`
      /* text / form cards: ha-card's own header spacing (as System → General); the 8px variant of
         sharedStyles is for cards that continue with list rows */
      .card-header {
        padding-bottom: var(--ha-space-6);
      }
      .card-content > p:first-child {
        margin-top: 0;
      }
      /* fallback list without ha-markdown: same metrics as ha-markdown's */
      ol {
        margin: 1em 0 0;
      }
      /* description → first field: 24px as in a config flow step (step-flow-form) */
      .card-content > ha-input {
        margin-top: var(--ha-space-6);
      }
      ha-markdown {
        color: var(--primary-text-color);
      }
      /* ha-input keeps 8px below its field; with ha-form's 16px the fields are 24px apart, as inside ha-form */
      ha-form {
        display: block;
        margin-top: var(--ha-space-4);
      }
      .card-actions.split {
        justify-content: space-between;
      }
      ha-progress-bar,
      progress {
        display: block;
        width: 100%;
        margin-top: var(--ha-space-4);
      }
      p.status {
        margin: var(--ha-space-2) 0 var(--ha-space-4);
      }
      ha-alert {
        margin-bottom: var(--ha-space-4);
      }
      .panels {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-2);
        /* as the outlined expansion panel of Backups → Settings (no haStyle there) */
        line-height: normal;
      }
      /* step rows sit in the panel's default 0 8px content padding, like ha-backup-config-schedule's rows */
      sep-step-list {
        --ha-row-item-padding-inline: 0;
      }
      ha-expansion-panel.log {
        --expansion-panel-content-padding: 0;
      }
      /* the log keeps the line height of the Logs page (haStyle) */
      sep-install-log {
        line-height: var(--ha-line-height-normal);
      }
      ha-expansion-panel ha-icon-button {
        color: var(--secondary-text-color);
        margin: -8px 0;
      }
    `]),G(`sep-install-tab`,fr);var pr=class extends w{constructor(){super(),this.options=[],this.selected=new Set,this._filter=``}_set(e){this.selected=e,this.dispatchEvent(new CustomEvent(`selection-changed`,{detail:{selected:e}}))}_toggle(e,t){let n=new Set(this.selected);t?n.add(e):n.delete(e),this._set(n)}get _visible(){let e=this._filter.trim().toLowerCase();return e?this.options.filter(t=>t.key.toLowerCase().includes(e)||(t.label??``).toLowerCase().includes(e)):this.options}render(){let e=this._visible,t=e=>this._filter=R(e);return v`
      <div class="top">
        ${N(`ha-input-search`)?v`<ha-input-search appearance="outlined" .value=${this._filter} @input=${t}></ha-input-search>`:v`<ha-input .placeholder=${`Search`} .value=${this._filter} @input=${t}></ha-input>`}
        <ha-button
          appearance="plain"
          size="s"
          @click=${()=>this._set(new Set([...this.selected,...e.map(e=>e.key)]))}
          >All</ha-button
        >
        <ha-button
          appearance="plain"
          size="s"
          @click=${()=>{let t=new Set(e.map(e=>e.key));this._set(new Set([...this.selected].filter(e=>!t.has(e))))}}
          >None</ha-button
        >
      </div>
      <div class="list">
        ${e.map(e=>v`
            <ha-checkbox .checked=${this.selected.has(e.key)} @change=${t=>this._toggle(e.key,z(t))}>
              ${e.label||e.key}
              ${e.label&&e.label!==e.key?v`<span class="secondary">(${e.key})</span>`:``}
            </ha-checkbox>
          `)}
        ${e.length?``:v`<div class="secondary pad">No matching settings.</div>`}
      </div>
      <div class="secondary count">${this.selected.size} of ${this.options.length} selected</div>
    `}};k(pr,`properties`,{options:{attribute:!1},selected:{attribute:!1},_filter:{state:!0}}),k(pr,`styles`,[U,o`
      :host {
        display: block;
      }
      .top {
        display: flex;
        align-items: center;
        gap: var(--ha-space-1);
        margin-bottom: var(--ha-space-2);
      }
      .top > :first-child {
        flex: 1;
        min-width: 0;
      }
      /* ha-backup-addons-picker */
      .list {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-2);
        padding-inline-start: var(--ha-space-2);
        padding-bottom: var(--ha-space-3);
      }
      .pad {
        padding: var(--ha-space-2);
      }
      .count {
        margin-top: var(--ha-space-1);
        font-size: var(--ha-font-size-s);
      }
    `]),G(`sep-key-picker`,pr);var mr={visible:!0,hidden:!1,unreachable:!1,missing:[],failed:[]},hr=(e,t,n=!1)=>JSON.stringify(e)===JSON.stringify(t)||n&&e!=null&&t!=null&&String(e)===String(t),gr=(e,t,n=!1)=>`eq`in e?hr(t,e.eq,n):`ne`in e?!hr(t,e.ne,n):Array.isArray(e.in)?e.in.some(e=>hr(t,e,n)):!1,_r=(e,t,n)=>{if(!n.has(e.cap))return!0;let r=t[e.cap];return e.min!==void 0&&e.min!==null?typeof r==`number`&&r>=e.min:typeof r==`boolean`?r:typeof r==`number`?r!==0:typeof r==`string`?r!==``:r!=null},vr=e=>e.type!==`bool`&&e.default,yr={state:`visible`,unreachable:!1,missing:[],failed:[]},br=class{constructor(e,t){k(this,`_value`,void 0),k(this,`_defs`,new Map),k(this,`_caps`,void 0),k(this,`_known`,void 0),k(this,`_loose`,void 0),k(this,`_cache`,new Map),this._value=t;for(let t of e.schema)this._defs.set(t.key,t);this._caps=e.capabilities??{},this._known=new Set(e.known_caps??Object.keys(this._caps)),this._loose=e.legacy??!1}def(e){return this._defs.get(e)}get(e){let t=this._defs.get(e);if(!t)return mr;if(t.hidden)return{...mr,visible:!1,hidden:!0};let{state:n,...r}=this._state(t,new Set);return{...r,visible:n===`visible`,hidden:!1}}visible(e){return this.get(e).visible}_state(e,t){let n=this._cache.get(e.key);if(n)return n;let r=(e.requires??[]).filter(e=>!_r(e,this._caps,this._known));if(r.length)return this._store(e.key,{state:`unavailable`,unreachable:!1,missing:r,failed:[]});let i=e.visible_if??[];if(!i.length)return this._store(e.key,yr);if(t.has(e.key))return{state:`inactive`,unreachable:!0,missing:[],failed:[]};t.add(e.key);let a=[],o=!1;try{for(let e of i){let n=this._defs.get(e.key);if(!n){o=!0;continue}let i=this._state(n,t);i.state===`inactive`?(r.push(...i.missing),a.push(...i.failed),o||=i.unreachable,gr(e,this._current(n),this._loose)||a.push({cond:e,parent:n})):i.state===`unavailable`?gr(e,vr(n),this._loose)||r.push(...i.missing):gr(e,this._current(n),this._loose)||a.push({cond:e,parent:n})}}finally{t.delete(e.key)}return!r.length&&!a.length&&!o?this._store(e.key,yr):this._store(e.key,{state:`inactive`,unreachable:o,missing:xr(r),failed:xr(a)})}_current(e){return this._value(e.key)??e.default}_store(e,t){return this._cache.set(e,t),t}},xr=e=>{let t=new Set;return e.filter(e=>{let n=JSON.stringify(e);return!t.has(n)&&(t.add(n),!0)})},Sr=(e,t)=>e?.options?.find(e=>hr(e.value,t,!0))?.label??an(t),Cr=({cond:e,parent:t})=>{let n=t?.label||e.key;return`eq`in e?typeof e.eq==`boolean`?`${n} is ${e.eq?`on`:`off`}`:`${n} is ${Sr(t,e.eq)}`:`ne`in e?typeof e.ne==`boolean`?`${n} is ${e.ne?`off`:`on`}`:`${n} is not ${Sr(t,e.ne)}`:`${n} is ${(e.in??[]).map(e=>Sr(t,e)).join(` or `)}`},wr=e=>e.visible?``:e.missing.length||e.unreachable||!e.failed.length?`Not available on this display`:`Shown when ${e.failed.map(Cr).join(` and `)}`,Tr={general:`General`,display:`Display`,screensaver:`Screensaver`,inputs:`Inputs & buttons`,mqtt:`MQTT`,voice:`Voice assistant`,bluetooth:`Bluetooth`,media:`Media`,advanced:`Advanced`},Er=Object.keys(Tr),Dr={deprecated:{header:`Deprecated`,secondary:`Settings of features the app will remove`},other:{header:`Not described by the display`,secondary:`Raw values the settings schema does not know`}},Or=Object.keys(Dr),kr=(e,t)=>JSON.stringify(e)===JSON.stringify(t),Ar=e=>Tr[e]??e.charAt(0).toUpperCase()+e.slice(1),jr=(e,t)=>t==null?``:e.type===`string_list`&&Array.isArray(t)?t.join(`, `):String(t),Mr=(e,t)=>{switch(e.type){case`int`:case`float`:{if(t.trim()===``)return[!1,null];let n=Number(t);return!Number.isFinite(n)||e.type===`int`&&!Number.isInteger(n)?[!1,null]:e.min!==null&&e.min!==void 0&&n<e.min||e.max!==null&&e.max!==void 0&&n>e.max?[!1,n]:[!0,n]}case`string_list`:return[!0,t.split(`,`).map(e=>e.trim()).filter(Boolean)];default:return[!0,t]}},Nr=[{value:`all`,label:`All portable settings`},{value:`selected`,label:`Only selected settings`}],Pr=class extends w{constructor(){super(),k(this,`_loadedFor`,``),k(this,`_reportedUnsaved`,``),k(this,`_openDialogName`,``),k(this,`_settingsSub`,void 0),k(this,`_subscribedFor`,``),k(this,`_dialogClosed`,B(()=>{this._dialog=``,this._openDialogName=``,this.requestUpdate()})),this.devices=[],this.entryId=``,this.narrow=!1,this._data=null,this._loading=!1,this._error=``,this._edits={},this._text={},this._invalid=new Set,this._filter=``,this._saving=!1,this._dialog=``,this._includeSecrets=!1,this._targets=[],this._keysMode=`all`,this._keys=new Set,this._profileName=``,this._profileDefault=!1,this._dialogBusy=!1}connectedCallback(){super.connectedCallback(),this._loadedFor&&this._subscribe(this._loadedFor)}disconnectedCallback(){super.disconnectedCallback(),this._unsubscribe()}willUpdate(e){(e.has(`entryId`)||e.has(`api`))&&this.api&&this.entryId&&this.entryId!==this._loadedFor&&this._load()}updated(){let e=this._dirty?Math.max(this._editCount,1):0,t=e?`${e}:${this.entryId}`:``;t!==this._reportedUnsaved&&(this._reportedUnsaved=t,V(this,`se-unsaved`,e?{count:e,name:this._device?.name??`the display`}:null))}get _device(){return this.devices.find(e=>e.entry_id===this.entryId)}get _editCount(){return Object.keys(this._edits).length}get _dirty(){return this._editCount>0||this._blockingInvalid.length>0}_evaluator(){return this._data?new br(this._data,e=>this._value(e)):null}get _blockingInvalid(){let e=this._evaluator();return[...this._invalid].filter(t=>!e||e.visible(t))}_resetEdits(){this._edits={},this._text={},this._invalid=new Set}async _load(){let e=this.entryId;this._data&&this._loadedFor!==e&&(this._data=null,this._resetEdits()),this._loadedFor=e,this._subscribedFor!==e&&this._subscribe(e),this._loading=!0,this._error=``;try{let t=await this.api.settingsGet(e);if(e!==this.entryId)return;this._data=t,this._resetEdits()}catch(t){if(e!==this.entryId)return;this._data=null,this._error=M(t)}finally{e===this.entryId&&(this._loading=!1)}}_subscribe(e){this._unsubscribe(),this._subscribedFor=e,this._settingsSub=this.api.subscribeSettings(e,t=>this._applyRemote(e,t)).catch(()=>void 0)}_unsubscribe(){let e=this._settingsSub;this._settingsSub=void 0,this._subscribedFor=``,e?.then(e=>e?.()).catch(()=>void 0)}_applyRemote(e,t){if(!this._data||e!==this._loadedFor||e!==this.entryId)return;let n={...this._edits},r={...this._text};for(let[e,i]of Object.entries(t))e in n&&!kr(n[e],i)||(delete n[e],this._invalid.has(e)||delete r[e]);this._data={...this._data,settings:{...this._data.settings,...t}},this._edits=n,this._text=r}async _reload(){return this._dirty&&!await this._confirmDiscard()?!1:(this._load(),!0)}_confirmDiscard(){return K(this,{title:`Discard unsaved changes?`,text:`${Z(this._editCount,`setting`)} changed on ${this._device?.name??`this display`} will be lost.`,confirmText:`Discard`,destructive:!0})}async _selectDevice(e){e&&e!==this.entryId&&(!this._dirty||await this._confirmDiscard())&&(this._resetEdits(),Qt(this,e))}_original(e){return this._data?.settings[e]}_value(e){return e in this._edits?this._edits[e]:this._original(e)}_setValue(e,t){let n={...this._edits};kr(t,this._original(e))?delete n[e]:n[e]=t,this._edits=n}_setText(e,t){this._text={...this._text,[e.key]:t};let[n,r]=Mr(e,t),i=new Set(this._invalid);n?(i.delete(e.key),this._setValue(e.key,r)):i.add(e.key),this._invalid=i}async _save(){if(!this._data||this._loading||this._loadedFor!==this.entryId||this._blockingInvalid.length)return;let e={...this._edits};for(let t of this._invalid)delete e[t];let t=Object.keys(e);if(t.length){this._saving=!0;try{let n=(await this.api.settingsSet(this.entryId,e)).ignored??[],r=t.filter(e=>!n.includes(e)),i=e=>this._data?.schema.find(t=>t.key===e)?.label||e,a=this._data.schema.filter(e=>e.requires_restart&&r.includes(e.key)),o=[...n.length?[`Not applied (the display does not know them): ${n.map(i).join(`, `)}`]:[],...a.length?[`Takes effect after an app restart: ${a.map(e=>e.label||e.key).join(`, `)}`]:[]],s=this._device?.name??`the display`;q(this,n.length?`Saved ${Z(r.length,`setting`)} on ${s}, not applied: ${n.map(i).join(`, `)}`:`Saved ${Z(r.length,`setting`)} on ${s}`,n.length?`warning`:`success`,o.length?o:void 0),await this._load()}catch(e){J(this,`Saving failed`,e)}finally{this._saving=!1}}}_portableKeyOptions(){if(!this._data)return[];let e=Ot(this._data);return this._data.schema.filter(t=>!e.has(t.key)&&!t.hidden&&!t.read_only).map(e=>({key:e.key,label:e.label??e.key}))}_openDialog(e){this._dialogBusy=!1,this._keysMode=`all`,this._keys=new Set,e===`copy`&&(this._targets=[]),e===`profile`&&(this._profileName=this._device?.name?`${this._device.name} profile`:``,this._profileDefault=!1),this._dialog=e,this._openDialogName=e}_closeDialog(){this._dialogBusy||(this._dialog=``)}async _runDialogAction(e,t){this._dialogBusy=!0;try{await t(),this._dialog=``}catch(t){J(this,e,t)}finally{this._dialogBusy=!1}}_export(){return this._runDialogAction(`Export failed`,async()=>{let e=await this.api.settingsExport(this.entryId,this._includeSecrets),t=new Date().toISOString().slice(0,10);$t(`${rn(this._device?.name??`display`)}-settings-${t}.json`,e)})}async _copy(){let e=[...this._targets],t=this._keysMode===`selected`?[...this._keys]:void 0;await K(this,{title:`Copy settings to ${Z(e.length,`display`)}?`,text:`${t?Z(t.length,`setting`):`All portable settings`} of ${this._device?.name} are written to the displays below. Per-display settings are never copied. A backup of each target is taken first.`,items:e.map(e=>j(this.devices,e)),confirmText:`Copy`})&&await this._runDialogAction(`Copy failed`,async()=>{let{results:n,errors:r}=await this.api.settingsCopy(this.entryId,e,t),i=e=>this.devices.find(t=>t.device_id===e||t.entry_id===e)?.name??e,a=Object.entries(r).map(([e,t])=>`${i(e)}: ${t}`),o=Object.entries(n);if(!o.length&&a.length)throw Error(a.join(`; `));let s=o.map(([e,t])=>`${i(e)}: ${t.length?Z(t.length,`setting`)+` changed`:`already up to date`}`);a.length?q(this,`Settings copied to ${o.length} of ${Z(e.length,`display`)}`,`warning`,[...a,...s]):q(this,`Settings copied to ${Z(e.length,`display`)}`,`success`,s)})}async _saveProfile(){let e=this._profileName.trim();e&&await this._runDialogAction(`Saving the profile failed`,async()=>{await this.api.profilesSave({name:e,from_entry_id:this.entryId,settings:this._editCount?{...this._edits}:void 0,keys:this._keysMode===`selected`?[...this._keys]:void 0,make_default:this._profileDefault||void 0}),q(this,`Profile “${e}” saved`,`success`)})}_renderControl(e,t){let n=this._value(e.key),r=this._invalid.has(e.key),i=e.secret||this._data?.secret.includes(e.key),a=e.label??e.key,o=this._loading||t;switch(e.type){case`bool`:return v`<ha-switch
          .checked=${n===!0}
          .disabled=${o}
          aria-label=${a}
          @change=${t=>this._setValue(e.key,z(t))}
        ></ha-switch>`;case`enum`:{let t=e.options??[],r=t.findIndex(e=>kr(e.value,n)||String(e.value)===String(n)),i=t.map((e,t)=>({value:String(t),label:e.label}));return r<0&&i.unshift({value:`-1`,label:an(n)}),v`<ha-select
          class="ctrl"
          .label=${void 0}
          aria-label=${a}
          .options=${i}
          .value=${String(r)}
          .disabled=${o}
          @selected=${n=>{n.stopPropagation();let r=Number(n.detail.value);r>=0&&t[r]&&this._setValue(e.key,t[r].value)}}
        ></ha-select>`}case`int`:case`float`:return v`<ha-input
          class="ctrl"
          .disabled=${o}
          type="number"
          aria-label=${a}
          .invalid=${r}
          .min=${e.min??void 0}
          .max=${e.max??void 0}
          .step=${e.step??(e.type===`int`?1:`any`)}
          .value=${this._text[e.key]??jr(e,n)}
          @input=${t=>this._setText(e,R(t))}
        >
          ${e.unit?v`<span slot="end" class="unit">${e.unit}</span>`:b}
        </ha-input>`;case`string_list`:return v`<ha-input
          class="ctrl"
          .disabled=${o}
          aria-label=${a}
          placeholder="value1, value2"
          .value=${this._text[e.key]??jr(e,n)}
          @input=${t=>this._setText(e,R(t))}
        ></ha-input>`;default:return v`<ha-input
          class="ctrl"
          .disabled=${o}
          aria-label=${a}
          .type=${i?`password`:`text`}
          ?password-toggle=${i}
          autocomplete=${i?`new-password`:`off`}
          .value=${n==null?``:String(n)}
          @input=${t=>this._setValue(e.key,R(t))}
        ></ha-input>`}}_renderField(e,t,n){let r=this._invalid.has(e.key),i=e.per_device||this._data?.per_device.includes(e.key),a=this._data?.managed?.[e.key],o=(e.type===`int`||e.type===`float`)&&(e.min!=null||e.max!=null)?`${e.min??`…`} – ${e.max??`…`}${e.unit?` ${e.unit}`:``}`:``,s=e.replaced_by?n.def(e.replaced_by)?.label??e.replaced_by:``,c=[e.key,o,i?`Per display`:``,e.requires_restart?`Requires an app restart`:``,s?`Replaced by ${s}`:``].filter(Boolean),l=t.visible?a??(e.read_only?`Read-only`:``):wr(t);return v`
      <ha-list-item-base class=${t.visible?``:`unavailable`}>
        <span slot="headline">${e.label||e.key}</span>
        <span slot="supporting-text"
          >${e.description?v`${e.description}<br />`:b}${c.join(` · `)}${l?v`<br /><span class="lock">${l}</span>`:b}${r?v`<br /><span class="error">Invalid value${o?` (${o})`:``}</span>`:b}</span
        >
        <div slot="end" class="end">${this._renderControl(e,!!l)}</div>
      </ha-list-item-base>
    `}_renderRows(e,t){return v`<ha-list-base class="rows">${e.map(e=>this._renderField(e,t.get(e.key),t))}</ha-list-base>`}_renderCategories(e){let t=this._evaluator();if(!t)return b;let n=this._filter.trim().toLowerCase(),r=new Map;for(let i of e.schema){if(i.hidden||n&&!i.key.toLowerCase().includes(n)&&!(i.label??``).toLowerCase().includes(n)||!n&&!t.visible(i.key))continue;let e=i.deprecated?`deprecated`:i.category||`general`;r.set(e,[...r.get(e)??[],i])}let i=e=>Er.includes(e)?Er.indexOf(e):99,a=[...r.keys()].filter(e=>!(e in Dr)).sort((e,t)=>i(e)-i(t)||e.localeCompare(t)),o=Or.filter(e=>r.has(e));return!a.length&&!o.length?n?v`<ha-card><div class="card-content">No settings match “${this._filter}”.</div></ha-card>`:b:v`
      ${a.map(e=>v`
          <ha-card>
            <h1 class="card-header">${Ar(e)}</h1>
            <div class="card-content list">${this._renderRows(r.get(e)??[],t)}</div>
          </ha-card>
        `)}
      ${o.map(e=>v`
          <ha-card>
            <ha-expansion-panel
              class="collapsed"
              .header=${Dr[e].header}
              .secondary=${Dr[e].secondary}
              .expanded=${!!n}
            >
              ${this._renderRows(r.get(e)??[],t)}
            </ha-expansion-panel>
          </ha-card>
        `)}
    `}_menu(){let e=this.devices.filter(A).length,t=!this._data;return e?{items:v`
        <ha-dropdown-item value="export" .disabled=${t}>
          <ha-svg-icon slot="icon" .path=${E}></ha-svg-icon>Export settings
        </ha-dropdown-item>
        <ha-dropdown-item value="copy" .disabled=${t||e<2}>
          <ha-svg-icon slot="icon" .path=${$e}></ha-svg-icon>Copy to other displays
        </ha-dropdown-item>
        <ha-dropdown-item value="profile" .disabled=${t}>
          <ha-svg-icon slot="icon" .path=${Qe}></ha-svg-icon>Save as profile
        </ha-dropdown-item>
      `,onSelect:e=>{(e===`export`||e===`copy`||e===`profile`)&&this._openDialog(e)},onReload:()=>this._reload()}:{}}_renderEditor(){if(!this._data)return this._loading?v`<div class="loading"><ha-spinner></ha-spinner></div>`:b;let e=this._device;return v`
      ${e&&!e.available?v`<ha-alert alert-type="warning" title="${e.name} is offline">
            Changes can only be saved while it is online.
          </ha-alert>`:b}
      ${this._device?.legacy?v`<ha-alert alert-type="info">
            This display runs the legacy app – settings use a built-in description and some may not apply.
          </ha-alert>`:b}
      ${this._renderCategories(this._data)}
    `}_renderSearch(){let e=e=>this._filter=R(e),t=this._data?.schema.filter(e=>!e.hidden).length??0,n=this._data?`Search ${Z(t,`setting`)}`:`Search settings`;return v`<div class="search">
      ${N(`ha-input-search`)?v`<ha-input-search
            appearance="outlined"
            .placeholder=${n}
            .value=${this._filter}
            .disabled=${!this._data}
            @input=${e}
          ></ha-input-search>`:v`<ha-input .placeholder=${n} .value=${this._filter} .disabled=${!this._data} @input=${e}></ha-input>`}
      ${zn(this.page.hass,this.devices,this.entryId,e=>this._selectDevice(e))}
    </div>`}_renderKeysChoice(){let e=[{name:`keys_mode`,required:!0,selector:{select:{mode:`list`,options:Nr}}}];return v`
      <ha-form
        .hass=${this.page.hass}
        .data=${{keys_mode:this._keysMode}}
        .schema=${e}
        .computeLabel=${()=>`Settings to include`}
        @value-changed=${e=>{e.stopPropagation(),this._keysMode=e.detail.value.keys_mode===`selected`?`selected`:`all`}}
      ></ha-form>
      ${this._keysMode===`selected`?v`<sep-key-picker
            .options=${this._portableKeyOptions()}
            .selected=${this._keys}
            @selection-changed=${e=>this._keys=e.detail.selected}
          ></sep-key-picker>`:b}
    `}_exportDialog(e){return{title:`Export settings`,body:v`
        <p class="dialog-text">
          Downloads the settings of <b>${this._device?.name}</b> as a JSON file. It can be imported as a profile.
        </p>
        <ha-form
          .hass=${this.page.hass}
          .data=${{include_secrets:this._includeSecrets}}
          .schema=${[{name:`include_secrets`,selector:{boolean:{}}}]}
          .computeLabel=${()=>`Include secrets`}
          .computeHelper=${()=>`Passwords and tokens`}
          @value-changed=${e=>{e.stopPropagation(),this._includeSecrets=!!e.detail.value.include_secrets}}
        ></ha-form>
        ${this._includeSecrets?v`<ha-alert alert-type="warning">Keep the file private – it contains credentials in plain text.</ha-alert>`:b}
      `,primary:v`<ha-button slot="primaryAction" .loading=${e} ?disabled=${e} @click=${this._export}>
        Download
      </ha-button>`}}_copyDialog(e,t){let n=this.devices.filter(e=>A(e)&&e.entry_id!==this.entryId),r=[{name:`targets`,selector:{select:{multiple:!0,mode:`list`,options:n.map(e=>({value:e.entry_id,label:`${e.name}${e.available?``:` (offline)`}`}))}}}];return{title:`Copy settings to other displays`,body:v`
        <div class="stack">
          ${this._editCount?v`<ha-alert alert-type="warning">Unsaved changes are not copied – save them first.</ha-alert>`:b}
          ${n.length?v`<ha-form
                .hass=${this.page.hass}
                .data=${{targets:this._targets}}
                .schema=${r}
                .computeLabel=${()=>`Target displays`}
                @value-changed=${e=>{e.stopPropagation(),this._targets=e.detail.value.targets??[]}}
              ></ha-form>`:v`<ha-alert alert-type="info">There are no other displays.</ha-alert>`}
          ${this._renderKeysChoice()}
        </div>
      `,primary:v`<ha-button
        slot="primaryAction"
        .loading=${e}
        ?disabled=${e||!this._targets.length||!t}
        @click=${this._copy}
      >
        Copy
      </ha-button>`}}_profileDialog(e,t){return{title:`Save as profile`,body:v`
        <div class="stack">
          <ha-form
            .hass=${this.page.hass}
            .data=${{name:this._profileName,make_default:this._profileDefault}}
            .schema=${[{name:`name`,required:!0,selector:{text:{}}},{name:`make_default`,selector:{boolean:{}}}]}
            .computeLabel=${e=>e.name===`name`?`Profile name`:`Default profile for new displays`}
            @value-changed=${e=>{e.stopPropagation(),this._profileName=e.detail.value.name??``,this._profileDefault=!!e.detail.value.make_default}}
          ></ha-form>
          ${this._editCount?v`<ha-alert alert-type="info">
                Your ${Z(this._editCount,`unsaved change`)} are included in the profile.
              </ha-alert>`:b}
          ${this._renderKeysChoice()}
        </div>
      `,primary:v`<ha-button
        slot="primaryAction"
        .loading=${e}
        ?disabled=${e||!this._profileName.trim()||!t}
        @click=${this._saveProfile}
      >
        Save profile
      </ha-button>`}}_dialogContent(e){let t=this._dialogBusy,n=this._keysMode===`all`||this._keys.size>0;switch(e){case`export`:return this._exportDialog(t);case`copy`:return this._copyDialog(t,n);case`profile`:return this._profileDialog(t,n);default:return null}}_renderDialog(){let e=this._dialogContent(this._dialog||this._openDialogName),t=this._dialogBusy;return v`
      <ha-dialog
        .open=${this._dialog!==``}
        width="medium"
        .headerTitle=${e?.title??``}
        .preventScrimClose=${t}
        @closed=${this._dialogClosed}
      >
        ${e?.body??b}
        <ha-dialog-footer slot="footer">
          <ha-button slot="secondaryAction" appearance="plain" ?disabled=${t} @click=${this._closeDialog}>Cancel</ha-button>
          ${e?.primary??b}
        </ha-dialog-footer>
      </ha-dialog>
    `}_renderContent(){return v`
      ${this._error?v`<ha-alert alert-type="error" title="Could not load the settings">
            ${this._error}
            <ha-button slot="action" appearance="plain" @click=${this._load}>Retry</ha-button>
          </ha-alert>`:b}
      ${this._renderEditor()}
    `}_fab(){return this._dirty?v`<ha-button
      slot="fab"
      size="l"
      .loading=${this._saving}
      ?disabled=${this._saving||this._loading||!this._editCount||this._blockingInvalid.length>0}
      @click=${this._save}
    >
      <ha-svg-icon slot="start" .path=${et}></ha-svg-icon>Save
    </ha-button>`:b}render(){if(!this.page)return b;let e=this.devices.some(A)?v`${this._renderSearch()}<div class="content">${this._renderContent()}</div>`:v`<div class="content">${Fn(this,this.devices)}</div>`;return v`
      ${Pn(this,this.page,e,this._fab(),this._menu())}
      ${this._renderDialog()}
    `}};k(Pr,`properties`,{page:{attribute:!1},api:{attribute:!1},devices:{attribute:!1},entryId:{},narrow:{type:Boolean,reflect:!0},_data:{state:!0},_loading:{state:!0},_error:{state:!0},_edits:{state:!0},_text:{state:!0},_invalid:{state:!0},_filter:{state:!0},_saving:{state:!0},_dialog:{state:!0},_includeSecrets:{state:!0},_targets:{state:!0},_keysMode:{state:!0},_keys:{state:!0},_profileName:{state:!0},_profileDefault:{state:!0},_dialogBusy:{state:!0}}),k(Pr,`styles`,[U,Bn,W,o`
      /* controls at the end of a row: ha-backup-config-schedule */
      .end {
        display: flex;
        align-items: center;
      }
      .end ha-select {
        min-width: 210px;
      }
      .end ha-input {
        width: 210px;
        /* no space reserved for a hint (errors are shown in the supporting text): 56px like ha-select */
        --ha-input-padding-bottom: 0;
      }
      /* below the sticky search bar the cards start 16px down, as on Settings → System → Logs */
      .search + .content {
        padding-top: var(--ha-space-4);
      }
      @media all and (max-width: 450px) {
        .end ha-select,
        .end ha-input {
          min-width: 160px;
          width: 160px;
        }
      }
      .unit {
        color: var(--secondary-text-color);
      }
      .lock {
        font-style: italic;
      }
      .unavailable [slot="headline"] {
        color: var(--disabled-text-color);
      }
      /* collapsed cards: the panel header takes the place of the card header */
      ha-expansion-panel.collapsed {
        --expansion-panel-summary-padding: var(--ha-space-2) var(--ha-space-4);
        --expansion-panel-content-padding: 0;
      }
      ha-form + ha-alert,
      ha-form + sep-key-picker {
        margin-top: var(--ha-space-2);
      }
    `]),G(`sep-settings-tab`,Pr);var Fr=`shellyelevateintegration.profile/1`,Ir=[{name:`name`,required:!0,selector:{text:{}}},{name:`make_default`,selector:{boolean:{}}}],Lr=e=>{if(!e.trim())return{settings:{}};try{let t=JSON.parse(e);if(!on(t))return{error:`The settings must be a JSON object: { "key": value, … }`};let n=Object.entries(t).filter(([,e])=>e===`**REDACTED**`).map(([e])=>e);return n.length?{error:`Redacted values cannot be saved: ${n.join(`, `)}`}:{settings:t}}catch(e){return{error:M(e)}}},Rr=e=>e.profileId?e.makeDefault===e.wasDefault?void 0:e.makeDefault:e.makeDefault||void 0,zr=(e,t)=>{if(!on(e))throw Error(`The file does not contain a JSON object`);let n=t.replace(/\.json$/i,``);if(on(e.settings))return typeof e.name==`string`?{settings:e.settings,name:e.name}:on(e.device)&&typeof e.device.name==`string`?{settings:e.settings,name:`${e.device.name} profile`}:{settings:e.settings,name:n};if(typeof e.format==`string`)throw Error(`Unsupported file format “${e.format}”`);return{settings:e,name:n}},Br=class extends w{constructor(){super(),this.devices=[],this.narrow=!1,this._profiles=null,this._loading=!1,this._error=``,this._editor=null,this._editorOpen=!1,this._saving=!1,this._fromEntry=``,this._fromBusy=!1,this._busyId=``}willUpdate(e){e.has(`api`)&&this.api&&this._load()}get _lang(){return this.page?.hass.locale?.language}async _load(){this._loading=!0;try{this._profiles=(await this.api.profilesList()).profiles,this._error=``}catch(e){this._error=M(e)}finally{this._loading=!1}}_openEditor(e){this._fromEntry=this.devices.find(A)?.entry_id??``,this._editor=e,this._editorOpen=!0}_new(e={},t=``){this._openEditor({name:t,json:JSON.stringify(e,null,2),makeDefault:!1,wasDefault:!1})}_edit(e){this._openEditor({profileId:e.id,name:e.name,json:JSON.stringify(e.settings,null,2),makeDefault:e.default,wasDefault:e.default})}_updateEditor(e){this._editor&&={...this._editor,...e}}async _fillFromDisplay(){if(!this._editor||!this._fromEntry)return;let e=Lr(this._editor.json);if(!(e.settings&&Object.keys(e.settings).length&&!await K(this,{title:`Replace the settings?`,text:`The editor content is replaced with the settings of the display.`,confirmText:`Replace`}))){this._fromBusy=!0;try{let e=await this.api.settingsGet(this._fromEntry),t=Ot(e),n=Object.fromEntries(Object.entries(e.settings).filter(([e])=>!t.has(e)).sort(([e],[t])=>e.localeCompare(t))),r=this.devices.find(e=>e.entry_id===this._fromEntry)?.name;this._updateEditor({json:JSON.stringify(n,null,2),name:this._editor?.name||(r?`${r} profile`:``)})}catch(e){J(this,`Could not read the display`,e)}finally{this._fromBusy=!1}}}async _saveEditor(){let e=this._editor;if(!e)return;let t=Lr(e.json),n=e.name.trim();if(t.settings&&n){this._saving=!0;try{await this.api.profilesSave({profile_id:e.profileId,name:n,settings:t.settings,make_default:Rr(e)}),q(this,`Profile “${n}” saved`,`success`),this._editorOpen=!1,await this._load()}catch(e){J(this,`Saving failed`,e)}finally{this._saving=!1}}}async _toggleDefault(e){this._busyId=e.id;try{await this.api.profilesSetDefault(e.default?null:e.id),await this._load()}catch(e){J(this,``,e)}finally{this._busyId=``}}async _delete(e){if(await K(this,{title:`Delete “${e.name}”?`,text:`The profile is deleted. Displays keep their current settings.${e.default?`

This is the default profile – no profile will be the default afterwards.`:``}`,confirmText:`Delete`,destructive:!0})){this._busyId=e.id;try{await this.api.profilesDelete(e.id),q(this,`Profile “${e.name}” deleted`,`success`),await this._load()}catch(e){J(this,`Delete failed`,e)}finally{this._busyId=``}}}_export(e){$t(`profile-${rn(e.name)}.json`,{format:Fr,exported:new Date().toISOString(),name:e.name,settings:e.settings})}async _import(){let e=await nn(`.json,application/json`);if(e)try{let{settings:t,name:n}=zr(JSON.parse(await e.text()),e.name);this._new(t,n),q(this,`Imported ${Z(Object.keys(t).length,`setting`)} from ${e.name} – review and save`,`info`)}catch(e){J(this,`Import failed`,e)}}async _apply(e){await this.updateComplete,this.renderRoot.querySelector(`sep-apply-profile-dialog`)?.show(e.id,[])}_onMenu(e,t){switch(t.detail.item.value){case`apply`:this._apply(e);break;case`default`:this._toggleDefault(e);break;case`edit`:this._edit(e);break;case`download`:this._export(e);break;case`delete`:this._delete(e)}}_renderFromDisplay(){let e=this.devices.filter(A);return e.length?v`<div class="from">
      <ha-select
        label="Take settings from a display"
        .options=${e.map(e=>({value:e.entry_id,label:e.name}))}
        .value=${this._fromEntry}
        @selected=${e=>{e.stopPropagation(),this._fromEntry=e.detail.value}}
      ></ha-select>
      <ha-button appearance="plain" .loading=${this._fromBusy} ?disabled=${this._fromBusy} @click=${this._fillFromDisplay}
        >Load</ha-button
      >
    </div>`:b}_renderJsonEditor(e,t){let n=t.settings?Object.keys(t.settings).length:0;return v`<div>
      <div class="editor-label">Settings (JSON)</div>
      ${N(`ha-code-editor`)?v`<ha-code-editor
            mode="yaml"
            .hass=${this.page.hass}
            .value=${e.json}
            .error=${!!t.error}
            disable-fullscreen
            in-dialog
            @value-changed=${e=>{e.stopPropagation(),this._updateEditor({json:e.detail.value})}}
          ></ha-code-editor>`:v`<textarea
            class="fallback"
            spellcheck="false"
            .value=${e.json}
            @input=${e=>this._updateEditor({json:e.currentTarget.value})}
          ></textarea>`}
      <div class="hint ${t.error?`error`:`secondary`}">
        ${t.error?t.error:v`Valid JSON · ${Z(n,`setting`)}. Per-display settings are removed when saving.`}
      </div>
    </div>`}_renderEditor(){let e=this._editor,t=e?Lr(e.json):{};return v`
      <ha-dialog
        .open=${this._editorOpen}
        width="large"
        .headerTitle=${e?.profileId?`Edit profile`:`New profile`}
        .preventScrimClose=${this._saving}
        @closed=${B(()=>{this._editorOpen=!1,this._editor=null})}
      >
        ${e?v`
              <div class="stack">
                <ha-form
                  .hass=${this.page.hass}
                  .data=${{name:e.name,make_default:e.makeDefault}}
                  .schema=${Ir}
                  .computeLabel=${e=>e.name===`name`?`Name`:`Default profile for new displays`}
                  .computeHelper=${e=>e.name===`make_default`?`Pre-selected when a new display is installed.`:void 0}
                  @value-changed=${e=>{e.stopPropagation(),this._updateEditor({name:e.detail.value.name??``,makeDefault:!!e.detail.value.make_default})}}
                ></ha-form>
                ${this._renderFromDisplay()} ${this._renderJsonEditor(e,t)}
              </div>
            `:b}
        <ha-dialog-footer slot="footer">
          <ha-button slot="secondaryAction" appearance="plain" ?disabled=${this._saving} @click=${()=>this._editorOpen=!1}
            >Cancel</ha-button
          >
          <ha-button
            slot="primaryAction"
            .loading=${this._saving}
            ?disabled=${this._saving||!!t.error||!e?.name.trim()}
            @click=${this._saveEditor}
          >
            Save
          </ha-button>
        </ha-dialog-footer>
      </ha-dialog>
    `}_renderProfile(e){let t=this._busyId===e.id;return v`
      <ha-list-item-button @click=${()=>this._edit(e)}>
        <ha-svg-icon slot="start" .path=${Qe}></ha-svg-icon>
        <span slot="headline">
          ${e.name} ${e.default?v`<ha-svg-icon .path=${gt} title="Default profile" role="img" aria-label="Default profile"></ha-svg-icon>`:b}
        </span>
        <span slot="supporting-text">
          ${Z(Object.keys(e.settings??{}).length,`setting`)} · Updated ${X(e.updated??e.created,this._lang)}
        </span>
        ${t?v`<ha-spinner slot="end" size="small"></ha-spinner>`:b}
        <ha-dropdown
          slot="end"
          placement="bottom-end"
          @click=${Q}
          @wa-select=${t=>this._onMenu(e,t)}
        >
          <ha-icon-button slot="trigger" .label=${`Menu`} .path=${T}></ha-icon-button>
          <ha-dropdown-item value="apply">
            <ha-svg-icon slot="icon" .path=${ut}></ha-svg-icon>Apply to displays
          </ha-dropdown-item>
          <ha-dropdown-item value="default" .disabled=${t}>
            <ha-svg-icon slot="icon" .path=${e.default?_t:vt}></ha-svg-icon>
            ${e.default?`Unset as default`:`Set as default`}
          </ha-dropdown-item>
          <ha-dropdown-item value="edit">
            <ha-svg-icon slot="icon" .path=${lt}></ha-svg-icon>Edit
          </ha-dropdown-item>
          <ha-dropdown-item value="download">
            <ha-svg-icon slot="icon" .path=${E}></ha-svg-icon>Download
          </ha-dropdown-item>
          <wa-divider></wa-divider>
          <ha-dropdown-item value="delete" variant="danger" .disabled=${t}>
            <ha-svg-icon slot="icon" .path=${tt}></ha-svg-icon>Delete
          </ha-dropdown-item>
        </ha-dropdown>
      </ha-list-item-button>
    `}_renderList(){return this._profiles===null?this._loading?v`<div class="loading"><ha-spinner></ha-spinner></div>`:b:this._profiles.length?v`<ha-list-base aria-label="Profiles">${this._profiles.map(e=>this._renderProfile(e))}</ha-list-base>`:b}_menu(){return{items:v`<ha-dropdown-item value="import">
        <ha-svg-icon slot="icon" .path=${bt}></ha-svg-icon>Import profile
      </ha-dropdown-item>`,onSelect:e=>{e===`import`&&this._import()}}}_renderContent(){let e=this._profiles!==null&&!this._profiles.length;return v`
      <div class="content">
        ${this._error?v`<ha-alert alert-type="error">${this._error}</ha-alert>`:b}
        <ha-card>
          <div class="card-header">Profiles</div>
          <div class="card-content list">
            <p>
              Profiles are named sets of settings you can apply to several displays. The default profile is used when a
              new display is installed. Per-display settings (IDs, names) are never part of a profile.
            </p>
            ${e?v`<p>No profiles yet. Create one, import a settings export or use “Save as profile” in the Settings tab.</p>`:b}
            ${this._renderList()}
          </div>
        </ha-card>
      </div>
    `}render(){if(!this.page)return b;let e=v`<ha-button slot="fab" size="l" @click=${()=>this._new()}>
      <ha-svg-icon slot="start" .path=${dt}></ha-svg-icon>New profile
    </ha-button>`;return v`
      ${Pn(this,this.page,this._renderContent(),e,this._menu())} ${this._renderEditor()}
      <sep-apply-profile-dialog
        .api=${this.api}
        .devices=${this.devices}
        .profiles=${this._profiles??[]}
        @applied=${()=>Jt(this)}
      ></sep-apply-profile-dialog>
    `}};k(Br,`properties`,{page:{attribute:!1},api:{attribute:!1},devices:{attribute:!1},narrow:{type:Boolean,reflect:!0},_profiles:{state:!0},_loading:{state:!0},_error:{state:!0},_editor:{state:!0},_editorOpen:{state:!0},_saving:{state:!0},_fromEntry:{state:!0},_fromBusy:{state:!0},_busyId:{state:!0}}),k(Br,`styles`,[U,Bn,W,o`
      /* ha-backup-overview-backups */
      .card-content.list {
        padding-left: 0;
        padding-right: 0;
      }
      .card-content.list > p {
        margin-left: var(--ha-space-4);
        margin-right: var(--ha-space-4);
      }
      /* assist-pref */
      ha-list-item-button span ha-svg-icon {
        color: currentColor;
        --mdc-icon-size: 16px;
        vertical-align: text-bottom;
      }
      .from {
        display: flex;
        align-items: center;
        gap: var(--ha-space-2);
      }
      .from ha-select {
        flex: 1;
        min-width: 0;
      }
      .editor-label {
        margin-bottom: var(--ha-space-2);
      }
      ha-code-editor {
        display: block;
        min-height: 240px;
        --code-mirror-max-height: 50vh;
      }
      .hint {
        margin-top: var(--ha-space-2);
        font-size: var(--ha-font-size-s);
      }
    `]),G(`sep-profiles-tab`,Br);var Vr={manual:[`Manual`,it],auto:[`Automatic`,Ke],setup:[`Setup`,Ke],before_restore:[`Before restore`,mt],before_profile:[`Before profile`,mt],before_update:[`Before update`,mt],import:[`Imported`,bt]},Hr=class extends w{constructor(){super(),k(this,`_loadedFor`,``),this.devices=[],this.entryId=``,this.narrow=!1,this._displayId=``,this._backups=null,this._all={},this._loading=!1,this._error=``,this._newName=``,this._createOpen=!1,this._creating=!1,this._source=``,this._diff=null,this._diffOpen=!1,this._busyId=``}willUpdate(e){(e.has(`entryId`)||e.has(`api`))&&this.api&&this.entryId&&this.entryId!==this._loadedFor&&this._load()}get _device(){return this.devices.find(e=>e.entry_id===this.entryId)}get _lang(){return this.page?.hass.locale?.language}async _load(){let e=this.entryId;this._loadedFor!==e&&(this._backups=null,this._displayId=``,this._all={},this._source=``),this._loadedFor=e,this._loading=!0,this._error=``;try{let[t,n]=await Promise.all([this.api.backupsList(e),this.api.backupsList()]);if(e!==this.entryId)return;let r=Object.keys(t)[0]??``;this._displayId=r,this._backups=t[r]??[],this._all=n;let i=this._otherIds;i.includes(this._source)||(this._source=i[0]??``)}catch(t){if(e!==this.entryId)return;this._error=M(t),this._backups=null}finally{e===this.entryId&&(this._loading=!1)}}get _otherIds(){return Object.keys(this._all).filter(e=>e!==this._displayId&&(this._all[e]?.length??0)>0).sort((e,t)=>this._label(e).localeCompare(this._label(t)))}_name(e){return this.devices.find(t=>A(t)&&t.display_id===e)?.name}_label(e){let t=this._name(e);if(t)return t;let n=this._all[e]?.[0]?.model;return`${e}${n?` (${n})`:``} – removed`}_openCreate(){this._newName=``,this._createOpen=!0}async _create(){this._creating=!0;try{let e=await this.api.backupsCreate(this.entryId,this._newName.trim()||void 0);q(this,`Backup created${e.name?`: ${e.name}`:``}`,`success`),this._creating=!1,this._createOpen=!1,await this._load()}catch(e){J(this,`Backup failed`,e)}finally{this._creating=!1}}async _openDiff(e,t){this._diff={backup:e,source:t,diff:null,selected:new Set,error:``,restoring:!1},this._diffOpen=!0;try{let n=await this.api.backupsDiff(this.entryId,e.id,t);if(this._diff?.backup.id!==e.id)return;this._diff={...this._diff,diff:n,selected:new Set(n.map(e=>e.key))}}catch(t){if(this._diff?.backup.id!==e.id)return;this._diff={...this._diff,error:M(t)}}}async _restore(){let e=this._diff;if(!e?.diff)return;let t=e.selected.size===e.diff.length,n=t?void 0:[...e.selected];if(await K(this,{title:`Restore ${Z(e.selected.size,`setting`)}?`,text:`${this._device?.name??`The display`} gets ${t?`all changed settings`:`the selected settings`} from the backup of ${X(e.backup.created,this._lang)}${e.source?` (from ${this._label(e.source)})`:``}.\n\nA backup of the current settings is taken first.`,confirmText:`Restore`,destructive:!0})){this._diff={...e,restoring:!0};try{let t=await this.api.backupsRestore(this.entryId,e.backup.id,n,e.source);q(this,`Restored ${Z(t.length,`setting`)} on ${this._device?.name??`the display`}`,`success`),this._diff={...e,restoring:!1},this._diffOpen=!1,await this._load()}catch(t){this._diff={...e,restoring:!1,error:M(t)}}}}async _delete(e,t){if(await K(this,{title:`Delete backup?`,text:`The backup${t.name?` “${t.name}”`:``} of ${this._label(e)} from ${X(t.created,this._lang)} will be permanently deleted.`,confirmText:`Delete`,destructive:!0})){this._busyId=t.id;try{await this.api.backupsDelete(e,t.id),q(this,`Backup deleted`,`success`),await this._load()}catch(e){J(this,`Delete failed`,e)}finally{this._busyId=``}}}_download(e,t){let n=this._name(e)??e;$t(`backup-${rn(n)}-${t.created.slice(0,19).replace(/[:T]/g,`-`)}.json`,{format:`shellyelevateintegration.backup/1`,device_id:e,device_name:n,...t})}_onMenu(e,t,n,r){switch(r.detail.item.value){case`restore`:this._openDiff(t,n);break;case`download`:this._download(e,t);break;case`delete`:this._delete(e,t)}}_renderList(e,t,n){return t.length?v`
      <ha-list-base aria-label="Backups">
        ${t.map(t=>{let[r,i]=Vr[t.reason]??[t.reason,`M12,3A9,9 0 0,0 3,12H0L4,16L8,12H5A7,7 0 0,1 12,5A7,7 0 0,1 19,12A7,7 0 0,1 12,19C10.5,19 9.09,18.5 7.94,17.7L6.5,19.14C8.04,20.3 9.94,21 12,21A9,9 0 0,0 21,12A9,9 0 0,0 12,3M14,12A2,2 0 0,0 12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12Z`],a=this._busyId===t.id;return v`
            <ha-list-item-button @click=${()=>this._openDiff(t,n)}>
              <ha-svg-icon slot="start" .path=${i}></ha-svg-icon>
              <span slot="headline">${t.name?t.name:X(t.created,this._lang)}</span>
              <span slot="supporting-text">
                ${t.name?v`${X(t.created,this._lang)} · `:b}${r} ·
                ${Z(Object.keys(t.settings??{}).length,`setting`)}${t.fw_version?` · Firmware ${t.fw_version}`:``}
              </span>
              ${a?v`<ha-spinner slot="end" size="small"></ha-spinner>`:b}
              <ha-dropdown
                slot="end"
                placement="bottom-end"
                @click=${Q}
                @wa-select=${r=>this._onMenu(e,t,n,r)}
              >
                <ha-icon-button slot="trigger" .label=${`Menu`} .path=${T}></ha-icon-button>
                <ha-dropdown-item value="restore">
                  <ha-svg-icon slot="icon" .path=${rt}></ha-svg-icon>Compare and restore
                </ha-dropdown-item>
                <ha-dropdown-item value="download">
                  <ha-svg-icon slot="icon" .path=${E}></ha-svg-icon>Download
                </ha-dropdown-item>
                <wa-divider></wa-divider>
                <ha-dropdown-item value="delete" variant="danger" .disabled=${a}>
                  <ha-svg-icon slot="icon" .path=${tt}></ha-svg-icon>Delete
                </ha-dropdown-item>
              </ha-dropdown>
            </ha-list-item-button>
          `})}
      </ha-list-base>
    `:v`<p>No backups yet.</p>`}_renderDiffBody(e){return v`
      <p class="dialog-text">
        Backup${e.backup.name?v` “${e.backup.name}”`:b}
        ${e.source?v`of <b>${this._label(e.source)}</b>`:b} compared with the current settings of
        <b>${this._device?.name}</b>.
      </p>
      ${e.source?v`<p class="dialog-text secondary">Per-display settings of the other display are left out.</p>`:b}
      ${e.error?v`<ha-alert alert-type="error">${e.error}</ha-alert>`:b}
      ${e.diff===null&&!e.error?v`<div class="loading"><ha-spinner></ha-spinner></div>`:b}
      ${e.diff?v`<sep-diff-table
            .diff=${e.diff}
            selectable
            .selected=${e.selected}
            empty-text="The display already has exactly these settings."
            @selection-changed=${t=>this._diff={...e,selected:t.detail.selected}}
          ></sep-diff-table>`:b}
    `}_renderDiffDialog(){let e=this._diff,t=!!e?.restoring;return v`
      <ha-dialog
        .open=${this._diffOpen}
        width="medium"
        header-title="Restore backup"
        .headerSubtitle=${e?X(e.backup.created,this._lang):void 0}
        .preventScrimClose=${t}
        @closed=${B(()=>{this._diffOpen=!1,this._diff=null})}
      >
        ${e?this._renderDiffBody(e):b}
        <ha-dialog-footer slot="footer">
          <ha-button slot="secondaryAction" appearance="plain" ?disabled=${t} @click=${()=>this._diffOpen=!1}
            >Cancel</ha-button
          >
          <ha-button
            slot="primaryAction"
            variant="danger"
            .loading=${t}
            ?disabled=${!e?.diff?.length||!e?.selected.size||t}
            @click=${this._restore}
          >
            ${e?.diff&&e.selected.size===e.diff.length?`Restore all`:`Restore ${e?.selected.size??0} selected`}
          </ha-button>
        </ha-dialog-footer>
      </ha-dialog>
    `}_renderCreateDialog(){return v`
      <ha-dialog
        .open=${this._createOpen}
        header-title="Create backup"
        .preventScrimClose=${this._creating}
        @closed=${B(()=>this._createOpen=!1)}
      >
        <p class="dialog-text">
          Saves the current settings of <b>${this._device?.name}</b>. Named backups are kept when old automatic ones are
          pruned.
        </p>
        <ha-input
          label="Name (optional)"
          autofocus
          .value=${this._newName}
          @input=${e=>this._newName=R(e)}
          @keydown=${e=>e.key===`Enter`&&!this._creating&&this._create()}
        ></ha-input>
        <ha-dialog-footer slot="footer">
          <ha-button slot="secondaryAction" appearance="plain" ?disabled=${this._creating} @click=${()=>this._createOpen=!1}
            >Cancel</ha-button
          >
          <ha-button slot="primaryAction" .loading=${this._creating} ?disabled=${this._creating} @click=${this._create}
            >Create backup</ha-button
          >
        </ha-dialog-footer>
      </ha-dialog>
    `}_renderOthers(e){return v`
      <ha-card>
        <div class="card-header">Restore from another display</div>
        <div class="card-content">
          <p>Apply a backup of a different (or removed) display to ${this._device?.name}. Per-display settings are skipped.</p>
          <ha-select
            label="Backups of"
            .options=${e.map(e=>({value:e,label:this._label(e)}))}
            .value=${this._source}
            @selected=${e=>{e.stopPropagation(),this._source=e.detail.value}}
          ></ha-select>
        </div>
        ${this._source?v`<div class="card-content list">
              ${this._renderList(this._source,this._all[this._source]??[],this._source)}
            </div>`:b}
      </ha-card>
    `}_renderContent(){if(!this.devices.some(A))return Fn(this,this.devices);let e=this._otherIds,t=this._device;return v`
      ${t&&!t.available?v`<ha-alert alert-type="warning" title="${t.name} is offline">
            Backups can be created and restored once it is back online.
          </ha-alert>`:b}
      ${this._error?v`<ha-alert alert-type="error" title="Could not load the backups">
            ${this._error}
            <ha-button slot="action" appearance="plain" @click=${this._load}>Retry</ha-button>
          </ha-alert>`:b}
      <ha-card>
        <div class="card-header">
          <span>My backups</span>
          ${zn(this.page.hass,this.devices,this.entryId,e=>Qt(this,e))}
        </div>
        <div class="card-content list">
          <p class="intro">
            Backups of the display settings are stored in Home Assistant and are part of Home Assistant backups.
          </p>
          ${this._backups===null?this._loading?v`<div class="loading"><ha-spinner></ha-spinner></div>`:b:this._renderList(this._displayId,this._backups)}
        </div>
      </ha-card>
      ${e.length?this._renderOthers(e):b}
    `}_menu(){return this.devices.some(A)?{onReload:()=>{this._load()}}:{}}render(){if(!this.page)return b;let e=this._device,t=e&&A(e)?v`<ha-button slot="fab" size="l" ?disabled=${!e.available} @click=${this._openCreate}>
            <ha-svg-icon slot="start" .path=${dt}></ha-svg-icon>Create backup
          </ha-button>`:b;return v`
      ${Pn(this,this.page,v`<div class="content">${this._renderContent()}</div>`,t,this._menu())}
      ${this._renderDiffDialog()} ${this._renderCreateDialog()}
    `}};k(Hr,`properties`,{page:{attribute:!1},api:{attribute:!1},devices:{attribute:!1},entryId:{},narrow:{type:Boolean,reflect:!0},_displayId:{state:!0},_backups:{state:!0},_all:{state:!0},_loading:{state:!0},_error:{state:!0},_newName:{state:!0},_createOpen:{state:!0},_creating:{state:!0},_source:{state:!0},_diff:{state:!0},_diffOpen:{state:!0},_busyId:{state:!0}}),k(Hr,`styles`,[U,Bn,W,o`
      /* "My backups" with the display picker at the end of the header; the button overlaps the
         header's padding so the header keeps the height of a plain one */
      .card-header:has(.display-picker) {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--ha-space-2);
      }
      .card-header .display-picker {
        margin-block: calc((var(--ha-line-height-condensed) * var(--ha-font-size-2xl) - 40px) / 2);
        font-size: var(--ha-font-size-m);
        letter-spacing: normal;
        line-height: normal;
      }
      .card-header > span {
        min-width: 0;
      }
      /* ha-backup-overview-backups */
      .card-content.list {
        padding-left: 0;
        padding-right: 0;
      }
      .card-content.list > p {
        margin-left: var(--ha-space-4);
        margin-right: var(--ha-space-4);
      }
    `]),G(`sep-backups-tab`,Hr),Tt();var Ur=[{id:`displays`,label:`Displays`,icon:D},{id:`install`,label:`Install`,icon:nt},{id:`settings`,label:`Settings`,icon:yt},{id:`profiles`,label:`Profiles`,icon:Qe},{id:`backups`,label:`Backups`,icon:Ge}],$=class extends w{constructor(){super(),k(this,`_api`,new At(()=>this.hass)),k(this,`_installVisited`,!1),k(this,`_loadedOnce`,!1),k(this,`_tabsCache`,null),k(this,`_unsaved`,null),k(this,`_onBeforeUnload`,e=>{this._unsaved&&e.preventDefault()}),k(this,`_confirmClosed`,B(()=>{this._confirm?.resolve(!1),this._confirm=null,this._confirmOpen=!1})),this.narrow=!1,this._tab=`displays`,this._devices=[],this._devicesError=``,this._loadingDevices=!1,this._entryId=``,this._confirm=null,this._confirmOpen=!1,this._ready=!1,this._missing=[],this._revertUsed=!1,this.addEventListener(`se-revert`,e=>{e.stopPropagation(),this._openRevert(e.detail)}),this.addEventListener(`se-confirm`,e=>{e.preventDefault(),e.stopPropagation(),this._confirm?.resolve(!1),this._confirm=e.detail,this._confirmOpen=!0}),this.addEventListener(`se-refresh-devices`,()=>this._loadDevices()),this.addEventListener(`se-open-tab`,async e=>{let{tab:t,entryId:n}=e.detail;(t===this._tab||await this._confirmLeave())&&(n&&(this._entryId=n),this._setTab(t))}),this.addEventListener(`se-entry-selected`,e=>{this._entryId=e.detail.entryId}),this.addEventListener(`se-unsaved`,e=>{this._unsaved=e.detail}),this.addEventListener(`click`,e=>this._guardLink(e),{capture:!0})}_guardLink(e){if(!this._unsaved||e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey)return;let t=e.composedPath().find(e=>e instanceof HTMLAnchorElement&&!!e.href);if(!t||t.target===`_blank`)return;let n=new URL(t.href);n.origin===location.origin&&n.pathname!==location.pathname&&(e.preventDefault(),e.stopPropagation(),this._confirmLeave().then(e=>e&&H(`${n.pathname}${n.search}`)))}async _confirmLeave(){let e=this._unsaved;if(!e)return!0;let t=await K(this,{title:`Discard unsaved changes?`,text:`${Z(e.count,`setting`)} changed on ${e.name} will be lost.`,confirmText:`Discard`,destructive:!0});return t&&(this._unsaved=null),t}connectedCallback(){super.connectedCallback(),Kt(this),window.addEventListener(`beforeunload`,this._onBeforeUnload),Rt().then(e=>{this._missing=e,this._ready=!0})}disconnectedCallback(){super.disconnectedCallback(),Kt(null),window.removeEventListener(`beforeunload`,this._onBeforeUnload)}get _prefix(){return this.route?.prefix??`/${this.panel?.url_path??`shelly-elevate`}`}willUpdate(e){if(e.has(`route`)&&this.route){let e=this.route.path.replace(/^\/+/,``).split(`/`)[0];Ur.some(t=>t.id===e)?(e!==`settings`&&(this._unsaved=null),this._tab=e):e||history.replaceState(history.state,``,`${this._prefix}/${this._tab}`)}e.has(`hass`)&&this.hass&&!this._loadedOnce&&(this._loadedOnce=!0,this._loadDevices())}async _loadDevices(){this._loadingDevices=!0;try{this._devices=await this._api.devices(),this._devicesError=``;let e=this._devices.filter(A);e.some(e=>e.entry_id===this._entryId)||(this._entryId=e[0]?.entry_id??``)}catch(e){this._devicesError=M(e)}finally{this._loadingDevices=!1}}async _openRevert(e){this._revertUsed=!0,await this.updateComplete,this.renderRoot.querySelector(`sep-revert-dialog`)?.show(e)}_setTab(e){e!==this._tab&&(this._tab=e,H(`${this._prefix}/${e}`,!0))}_resolveConfirm(e){let t=this._confirm;this._confirmOpen=!1,t&&(t.resolve(e),this._confirm={...t,resolve:()=>void 0})}_context(){let e=this._prefix;return this._tabsCache?.prefix!==e&&(this._tabsCache={prefix:e,tabs:Ur.map(t=>({path:`${e}/${t.id}`,name:t.label,iconPath:t.icon}))}),{hass:this.hass,route:{prefix:e,path:`/${this._tab}`},tabs:this._tabsCache.tabs,narrow:this.narrow,version:this.panel?.config?.version}}_renderTab(e){switch(this._tab){case`install`:return b;case`settings`:return v`<sep-settings-tab
          .page=${e}
          .api=${this._api}
          .devices=${this._devices}
          .entryId=${this._entryId}
          ?narrow=${this.narrow}
        ></sep-settings-tab>`;case`profiles`:return v`<sep-profiles-tab .page=${e} .api=${this._api} .devices=${this._devices} ?narrow=${this.narrow}></sep-profiles-tab>`;case`backups`:return v`<sep-backups-tab
          .page=${e}
          .api=${this._api}
          .devices=${this._devices}
          .entryId=${this._entryId}
          ?narrow=${this.narrow}
        ></sep-backups-tab>`;default:return v`<sep-displays-tab
          .page=${e}
          .api=${this._api}
          .devices=${this._devices}
          .loading=${this._loadingDevices}
          .error=${this._devicesError}
          ?narrow=${this.narrow}
        ></sep-displays-tab>`}}_renderConfirm(){let e=this._confirm;return e?v`
      <ha-dialog
        .open=${this._confirmOpen}
        type=${e.alert?`standard`:`alert`}
        ?prevent-scrim-close=${!e.alert}
        aria-labelledby="se-confirm-title"
        aria-describedby="se-confirm-description"
        @closed=${this._confirmClosed}
      >
        <!-- Same header as HA's own confirmation dialog (dialog-box): close button only for alerts. -->
        <ha-dialog-header slot="header">
          ${e.alert?v`<ha-icon-button
                slot="navigationIcon"
                data-dialog="close"
                .label=${`Close`}
                .path=${Xe}
              ></ha-icon-button>`:b}
          <h1 slot="title" class="title ${e.alert?``:`alert`}" id="se-confirm-title">${e.title}</h1>
        </ha-dialog-header>
        <div id="se-confirm-description">
          ${e.text?v`<p class="confirm-text">${e.text}</p>`:b}
          ${e.items?.length?v`<ul class="items">${e.items.map(e=>v`<li>${e}</li>`)}</ul>`:b}
        </div>
        <ha-dialog-footer slot="footer">
          ${e.alert?b:v`<ha-button
                slot="secondaryAction"
                appearance="plain"
                ?autofocus=${!!e.destructive}
                @click=${()=>this._resolveConfirm(!1)}
              >
                ${e.dismissText??`Cancel`}
              </ha-button>`}
          <ha-button
            slot="primaryAction"
            variant=${e.destructive?`danger`:`brand`}
            ?autofocus=${!e.destructive}
            @click=${()=>this._resolveConfirm(!0)}
          >
            ${e.confirmText??`OK`}
          </ha-button>
        </ha-dialog-footer>
      </ha-dialog>
    `:b}render(){if(!this.hass||!this._ready)return v`<div class="loading"><ha-spinner size="large"></ha-spinner></div>`;let e=this._missing.filter(e=>jt.includes(e));if(e.length)return v`<div class="unsupported">
        <h1>Shelly Elevate</h1>
        <p>
          This Home Assistant frontend does not provide the components the panel needs
          (${e.join(`, `)}). Reload the page; if this persists, update Home Assistant.
        </p>
        <button @click=${()=>location.reload()}>Reload</button>
      </div>`;this._tab===`install`&&(this._installVisited=!0);let t=this._context();return v`
      ${this._renderTab(t)}
      ${this._installVisited?v`<sep-install-tab
            class=${this._tab===`install`?``:`hidden`}
            .page=${t}
            .api=${this._api}
            .devices=${this._devices}
            .active=${this._tab===`install`}
            ?narrow=${this.narrow}
          ></sep-install-tab>`:b}
      ${this._revertUsed?v`<sep-revert-dialog .api=${this._api} .devices=${this._devices}></sep-revert-dialog>`:b}
      ${this._renderConfirm()}
    `}};k($,`bundle`,import.meta.url),k($,`properties`,{hass:{attribute:!1},narrow:{type:Boolean,reflect:!0},route:{attribute:!1},panel:{attribute:!1},_tab:{state:!0},_devices:{state:!0},_devicesError:{state:!0},_loadingDevices:{state:!0},_entryId:{state:!0},_confirm:{state:!0},_confirmOpen:{state:!0},_ready:{state:!0},_missing:{state:!0},_revertUsed:{state:!0}}),k($,`styles`,[U,W,o`
      :host {
        display: block;
        height: 100%;
        background: var(--primary-background-color);
      }
      .loading {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
      }
      .unsupported {
        padding: var(--ha-space-6);
        max-width: 640px;
        margin: 0 auto;
      }
      /* dialog-box */
      p {
        margin: 0;
        color: var(--primary-text-color);
      }
      .confirm-text {
        white-space: pre-line;
      }
      .title {
        font-weight: inherit;
        font-size: inherit;
        margin: inherit;
      }
      .title.alert {
        padding: 0 var(--ha-space-2);
      }
      @media all and (min-width: 450px) and (min-height: 500px) {
        .title.alert {
          padding: 0 var(--ha-space-1);
        }
      }
      .items {
        margin: var(--ha-space-2) 0 0;
        padding-inline-start: var(--ha-space-5);
      }
      .items li {
        margin-bottom: var(--ha-space-1);
      }
    `]);var Wr=customElements.get(`shelly-elevate-panel`);Wr&&Wr.bundle!==$.bundle&&location.reload(),G(`shelly-elevate-panel`,$);