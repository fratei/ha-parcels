var et=globalThis,tt=et.ShadowRoot&&(et.ShadyCSS===void 0||et.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,Dt=Symbol(),Or=new WeakMap,Ne=class{constructor(e,r,i){if(this._$cssResult$=!0,i!==Dt)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=r}get styleSheet(){let e=this.o,r=this.t;if(tt&&e===void 0){let i=r!==void 0&&r.length===1;i&&(e=Or.get(r)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&Or.set(r,e))}return e}toString(){return this.cssText}},Mr=t=>new Ne(typeof t=="string"?t:t+"",void 0,Dt),R=(t,...e)=>{let r=t.length===1?t[0]:e.reduce((i,n,o)=>i+(a=>{if(a._$cssResult$===!0)return a.cssText;if(typeof a=="number")return a;throw Error("Value passed to 'css' function must be a 'css' function result: "+a+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(n)+t[o+1],t[0]);return new Ne(r,t,Dt)},Nr=(t,e)=>{if(tt)t.adoptedStyleSheets=e.map(r=>r instanceof CSSStyleSheet?r:r.styleSheet);else for(let r of e){let i=document.createElement("style"),n=et.litNonce;n!==void 0&&i.setAttribute("nonce",n),i.textContent=r.cssText,t.appendChild(i)}},Ft=tt?t=>t:t=>t instanceof CSSStyleSheet?(e=>{let r="";for(let i of e.cssRules)r+=i.cssText;return Mr(r)})(t):t;var{is:es,defineProperty:ts,getOwnPropertyDescriptor:rs,getOwnPropertyNames:is,getOwnPropertySymbols:ns,getPrototypeOf:ss}=Object,rt=globalThis,Dr=rt.trustedTypes,os=Dr?Dr.emptyScript:"",as=rt.reactiveElementPolyfillSupport,De=(t,e)=>t,Ht={toAttribute(t,e){switch(e){case Boolean:t=t?os:null;break;case Object:case Array:t=t==null?t:JSON.stringify(t)}return t},fromAttribute(t,e){let r=t;switch(e){case Boolean:r=t!==null;break;case Number:r=t===null?null:Number(t);break;case Object:case Array:try{r=JSON.parse(t)}catch{r=null}}return r}},Hr=(t,e)=>!es(t,e),Fr={attribute:!0,type:String,converter:Ht,reflect:!1,useDefault:!1,hasChanged:Hr};Symbol.metadata??=Symbol("metadata"),rt.litPropertyMetadata??=new WeakMap;var J=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,r=Fr){if(r.state&&(r.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((r=Object.create(r)).wrapped=!0),this.elementProperties.set(e,r),!r.noAccessor){let i=Symbol(),n=this.getPropertyDescriptor(e,i,r);n!==void 0&&ts(this.prototype,e,n)}}static getPropertyDescriptor(e,r,i){let{get:n,set:o}=rs(this.prototype,e)??{get(){return this[r]},set(a){this[r]=a}};return{get:n,set(a){let c=n?.call(this);o?.call(this,a),this.requestUpdate(e,c,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??Fr}static _$Ei(){if(this.hasOwnProperty(De("elementProperties")))return;let e=ss(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(De("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(De("properties"))){let r=this.properties,i=[...is(r),...ns(r)];for(let n of i)this.createProperty(n,r[n])}let e=this[Symbol.metadata];if(e!==null){let r=litPropertyMetadata.get(e);if(r!==void 0)for(let[i,n]of r)this.elementProperties.set(i,n)}this._$Eh=new Map;for(let[r,i]of this.elementProperties){let n=this._$Eu(r,i);n!==void 0&&this._$Eh.set(n,r)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let r=[];if(Array.isArray(e)){let i=new Set(e.flat(1/0).reverse());for(let n of i)r.unshift(Ft(n))}else e!==void 0&&r.push(Ft(e));return r}static _$Eu(e,r){let i=r.attribute;return i===!1?void 0:typeof i=="string"?i:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,r=this.constructor.elementProperties;for(let i of r.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Nr(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,r,i){this._$AK(e,i)}_$ET(e,r){let i=this.constructor.elementProperties.get(e),n=this.constructor._$Eu(e,i);if(n!==void 0&&i.reflect===!0){let o=(i.converter?.toAttribute!==void 0?i.converter:Ht).toAttribute(r,i.type);this._$Em=e,o==null?this.removeAttribute(n):this.setAttribute(n,o),this._$Em=null}}_$AK(e,r){let i=this.constructor,n=i._$Eh.get(e);if(n!==void 0&&this._$Em!==n){let o=i.getPropertyOptions(n),a=typeof o.converter=="function"?{fromAttribute:o.converter}:o.converter?.fromAttribute!==void 0?o.converter:Ht;this._$Em=n;let c=a.fromAttribute(r,o.type);this[n]=c??this._$Ej?.get(n)??c,this._$Em=null}}requestUpdate(e,r,i,n=!1,o){if(e!==void 0){let a=this.constructor;if(n===!1&&(o=this[e]),i??=a.getPropertyOptions(e),!((i.hasChanged??Hr)(o,r)||i.useDefault&&i.reflect&&o===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,i))))return;this.C(e,r,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,r,{useDefault:i,reflect:n,wrapped:o},a){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??r??this[e]),o!==!0||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||i||(r=void 0),this._$AL.set(e,r)),n===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(r){Promise.reject(r)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[n,o]of this._$Ep)this[n]=o;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[n,o]of i){let{wrapped:a}=o,c=this[n];a!==!0||this._$AL.has(n)||c===void 0||this.C(n,void 0,o,c)}}let e=!1,r=this._$AL;try{e=this.shouldUpdate(r),e?(this.willUpdate(r),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(r)):this._$EM()}catch(i){throw e=!1,this._$EM(),i}e&&this._$AE(r)}willUpdate(e){}_$AE(e){this._$EO?.forEach(r=>r.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(r=>this._$ET(r,this[r])),this._$EM()}updated(e){}firstUpdated(e){}};J.elementStyles=[],J.shadowRootOptions={mode:"open"},J[De("elementProperties")]=new Map,J[De("finalized")]=new Map,as?.({ReactiveElement:J}),(rt.reactiveElementVersions??=[]).push("2.1.2");var Bt=globalThis,Ur=t=>t,it=Bt.trustedTypes,Br=it?it.createPolicy("lit-html",{createHTML:t=>t}):void 0,zt="$lit$",X=`lit$${Math.random().toFixed(9).slice(2)}$`,jt="?"+X,ls=`<${jt}>`,fe=document,He=()=>fe.createComment(""),Ue=t=>t===null||typeof t!="object"&&typeof t!="function",Kt=Array.isArray,Gr=t=>Kt(t)||typeof t?.[Symbol.iterator]=="function",Ut=`[ 	
\f\r]`,Fe=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,zr=/-->/g,jr=/>/g,he=RegExp(`>|${Ut}(?:([^\\s"'>=/]+)(${Ut}*=${Ut}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Kr=/'/g,Wr=/"/g,Vr=/^(?:script|style|textarea|title)$/i,Wt=t=>(e,...r)=>({_$litType$:t,strings:e,values:r}),l=Wt(1),ia=Wt(2),na=Wt(3),k=Symbol.for("lit-noChange"),u=Symbol.for("lit-nothing"),qr=new WeakMap,me=fe.createTreeWalker(fe,129);function Yr(t,e){if(!Kt(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return Br!==void 0?Br.createHTML(e):e}var Qr=(t,e)=>{let r=t.length-1,i=[],n,o=e===2?"<svg>":e===3?"<math>":"",a=Fe;for(let c=0;c<r;c++){let d=t[c],m,g,h=-1,_=0;for(;_<d.length&&(a.lastIndex=_,g=a.exec(d),g!==null);)_=a.lastIndex,a===Fe?g[1]==="!--"?a=zr:g[1]!==void 0?a=jr:g[2]!==void 0?(Vr.test(g[2])&&(n=RegExp("</"+g[2],"g")),a=he):g[3]!==void 0&&(a=he):a===he?g[0]===">"?(a=n??Fe,h=-1):g[1]===void 0?h=-2:(h=a.lastIndex-g[2].length,m=g[1],a=g[3]===void 0?he:g[3]==='"'?Wr:Kr):a===Wr||a===Kr?a=he:a===zr||a===jr?a=Fe:(a=he,n=void 0);let f=a===he&&t[c+1].startsWith("/>")?" ":"";o+=a===Fe?d+ls:h>=0?(i.push(m),d.slice(0,h)+zt+d.slice(h)+X+f):d+X+(h===-2?c:f)}return[Yr(t,o+(t[r]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),i]},Be=class t{constructor({strings:e,_$litType$:r},i){let n;this.parts=[];let o=0,a=0,c=e.length-1,d=this.parts,[m,g]=Qr(e,r);if(this.el=t.createElement(m,i),me.currentNode=this.el.content,r===2||r===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(n=me.nextNode())!==null&&d.length<c;){if(n.nodeType===1){if(n.hasAttributes())for(let h of n.getAttributeNames())if(h.endsWith(zt)){let _=g[a++],f=n.getAttribute(h).split(X),v=/([.?@])?(.*)/.exec(_);d.push({type:1,index:o,name:v[2],strings:f,ctor:v[1]==="."?st:v[1]==="?"?ot:v[1]==="@"?at:_e}),n.removeAttribute(h)}else h.startsWith(X)&&(d.push({type:6,index:o}),n.removeAttribute(h));if(Vr.test(n.tagName)){let h=n.textContent.split(X),_=h.length-1;if(_>0){n.textContent=it?it.emptyScript:"";for(let f=0;f<_;f++)n.append(h[f],He()),me.nextNode(),d.push({type:2,index:++o});n.append(h[_],He())}}}else if(n.nodeType===8)if(n.data===jt)d.push({type:2,index:o});else{let h=-1;for(;(h=n.data.indexOf(X,h+1))!==-1;)d.push({type:7,index:o}),h+=X.length-1}o++}}static createElement(e,r){let i=fe.createElement("template");return i.innerHTML=e,i}};function ge(t,e,r=t,i){if(e===k)return e;let n=i!==void 0?r._$Co?.[i]:r._$Cl,o=Ue(e)?void 0:e._$litDirective$;return n?.constructor!==o&&(n?._$AO?.(!1),o===void 0?n=void 0:(n=new o(t),n._$AT(t,r,i)),i!==void 0?(r._$Co??=[])[i]=n:r._$Cl=n),n!==void 0&&(e=ge(t,n._$AS(t,e.values),n,i)),e}var nt=class{constructor(e,r){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=r}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:r},parts:i}=this._$AD,n=(e?.creationScope??fe).importNode(r,!0);me.currentNode=n;let o=me.nextNode(),a=0,c=0,d=i[0];for(;d!==void 0;){if(a===d.index){let m;d.type===2?m=new Se(o,o.nextSibling,this,e):d.type===1?m=new d.ctor(o,d.name,d.strings,this,e):d.type===6&&(m=new lt(o,this,e)),this._$AV.push(m),d=i[++c]}a!==d?.index&&(o=me.nextNode(),a++)}return me.currentNode=fe,n}p(e){let r=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(e,i,r),r+=i.strings.length-2):i._$AI(e[r])),r++}},Se=class t{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,r,i,n){this.type=2,this._$AH=u,this._$AN=void 0,this._$AA=e,this._$AB=r,this._$AM=i,this.options=n,this._$Cv=n?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,r=this._$AM;return r!==void 0&&e?.nodeType===11&&(e=r.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,r=this){e=ge(this,e,r),Ue(e)?e===u||e==null||e===""?(this._$AH!==u&&this._$AR(),this._$AH=u):e!==this._$AH&&e!==k&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):Gr(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==u&&Ue(this._$AH)?this._$AA.nextSibling.data=e:this.T(fe.createTextNode(e)),this._$AH=e}$(e){let{values:r,_$litType$:i}=e,n=typeof i=="number"?this._$AC(e):(i.el===void 0&&(i.el=Be.createElement(Yr(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===n)this._$AH.p(r);else{let o=new nt(n,this),a=o.u(this.options);o.p(r),this.T(a),this._$AH=o}}_$AC(e){let r=qr.get(e.strings);return r===void 0&&qr.set(e.strings,r=new Be(e)),r}k(e){Kt(this._$AH)||(this._$AH=[],this._$AR());let r=this._$AH,i,n=0;for(let o of e)n===r.length?r.push(i=new t(this.O(He()),this.O(He()),this,this.options)):i=r[n],i._$AI(o),n++;n<r.length&&(this._$AR(i&&i._$AB.nextSibling,n),r.length=n)}_$AR(e=this._$AA.nextSibling,r){for(this._$AP?.(!1,!0,r);e!==this._$AB;){let i=Ur(e).nextSibling;Ur(e).remove(),e=i}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},_e=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,r,i,n,o){this.type=1,this._$AH=u,this._$AN=void 0,this.element=e,this.name=r,this._$AM=n,this.options=o,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=u}_$AI(e,r=this,i,n){let o=this.strings,a=!1;if(o===void 0)e=ge(this,e,r,0),a=!Ue(e)||e!==this._$AH&&e!==k,a&&(this._$AH=e);else{let c=e,d,m;for(e=o[0],d=0;d<o.length-1;d++)m=ge(this,c[i+d],r,d),m===k&&(m=this._$AH[d]),a||=!Ue(m)||m!==this._$AH[d],m===u?e=u:e!==u&&(e+=(m??"")+o[d+1]),this._$AH[d]=m}a&&!n&&this.j(e)}j(e){e===u?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},st=class extends _e{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===u?void 0:e}},ot=class extends _e{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==u)}},at=class extends _e{constructor(e,r,i,n,o){super(e,r,i,n,o),this.type=5}_$AI(e,r=this){if((e=ge(this,e,r,0)??u)===k)return;let i=this._$AH,n=e===u&&i!==u||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,o=e!==u&&(i===u||n);n&&this.element.removeEventListener(this.name,this,i),o&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},lt=class{constructor(e,r,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=r,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){ge(this,e)}},Zr={M:zt,P:X,A:jt,C:1,L:Qr,R:nt,D:Gr,V:ge,I:Se,H:_e,N:ot,U:at,B:st,F:lt},cs=Bt.litHtmlPolyfillSupport;cs?.(Be,Se),(Bt.litHtmlVersions??=[]).push("3.3.3");var Jr=(t,e,r)=>{let i=r?.renderBefore??e,n=i._$litPart$;if(n===void 0){let o=r?.renderBefore??null;i._$litPart$=n=new Se(e.insertBefore(He(),o),o,void 0,r??{})}return n._$AI(t),n};var qt=globalThis,Y=class extends J{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let r=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Jr(r,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return k}};Y._$litElement$=!0,Y.finalized=!0,qt.litElementHydrateSupport?.({LitElement:Y});var ds=qt.litElementPolyfillSupport;ds?.({LitElement:Y});(qt.litElementVersions??=[]).push("4.2.2");var N={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},ne=t=>(...e)=>({_$litDirective$:t,values:e}),Q=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,r,i){this._$Ct=e,this._$AM=r,this._$Ci=i}_$AS(e,r){return this.update(e,r)}update(e,r){return this.render(...r)}};var{I:us}=Zr,Xr=t=>t;var ti=t=>t.strings===void 0,ei=()=>document.createComment(""),Re=(t,e,r)=>{let i=t._$AA.parentNode,n=e===void 0?t._$AB:e._$AA;if(r===void 0){let o=i.insertBefore(ei(),n),a=i.insertBefore(ei(),n);r=new us(o,a,t,t.options)}else{let o=r._$AB.nextSibling,a=r._$AM,c=a!==t;if(c){let d;r._$AQ?.(t),r._$AM=t,r._$AP!==void 0&&(d=t._$AU)!==a._$AU&&r._$AP(d)}if(o!==n||c){let d=r._$AA;for(;d!==o;){let m=Xr(d).nextSibling;Xr(i).insertBefore(d,n),d=m}}}return r},se=(t,e,r=t)=>(t._$AI(e,r),t),ps={},ct=(t,e=ps)=>t._$AH=e,ri=t=>t._$AH,dt=t=>{t._$AR(),t._$AA.remove()};var ii=(t,e,r)=>{let i=new Map;for(let n=e;n<=r;n++)i.set(t[n],n);return i},ee=ne(class extends Q{constructor(t){if(super(t),t.type!==N.CHILD)throw Error("repeat() can only be used in text expressions")}dt(t,e,r){let i;r===void 0?r=e:e!==void 0&&(i=e);let n=[],o=[],a=0;for(let c of t)n[a]=i?i(c,a):a,o[a]=r(c,a),a++;return{values:o,keys:n}}render(t,e,r){return this.dt(t,e,r).values}update(t,[e,r,i]){let n=ri(t),{values:o,keys:a}=this.dt(e,r,i);if(!Array.isArray(n))return this.ut=a,o;let c=this.ut??=[],d=[],m,g,h=0,_=n.length-1,f=0,v=o.length-1;for(;h<=_&&f<=v;)if(n[h]===null)h++;else if(n[_]===null)_--;else if(c[h]===a[f])d[f]=se(n[h],o[f]),h++,f++;else if(c[_]===a[v])d[v]=se(n[_],o[v]),_--,v--;else if(c[h]===a[v])d[v]=se(n[h],o[v]),Re(t,d[v+1],n[h]),h++,v--;else if(c[_]===a[f])d[f]=se(n[_],o[f]),Re(t,n[h],n[_]),_--,f++;else if(m===void 0&&(m=ii(a,f,v),g=ii(c,h,_)),m.has(c[h]))if(m.has(c[_])){let A=g.get(a[f]),T=A!==void 0?n[A]:null;if(T===null){let S=Re(t,n[h]);se(S,o[f]),d[f]=S}else d[f]=se(T,o[f]),Re(t,n[h],T),n[A]=null;f++}else dt(n[_]),_--;else dt(n[h]),h++;for(;f<=v;){let A=Re(t,d[v+1]);se(A,o[f]),d[f++]=A}for(;h<=_;){let A=n[h++];A!==null&&dt(A)}return this.ut=a,ct(t,d),k}});var ni="important",hs=" !"+ni,z=ne(class extends Q{constructor(t){if(super(t),t.type!==N.ATTRIBUTE||t.name!=="style"||t.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(t){return Object.keys(t).reduce((e,r)=>{let i=t[r];return i==null?e:e+`${r=r.includes("-")?r:r.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${i};`},"")}update(t,[e]){let{style:r}=t.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(e)),this.render(e);for(let i of this.ft)e[i]==null&&(this.ft.delete(i),i.includes("-")?r.removeProperty(i):r[i]=null);for(let i in e){let n=e[i];if(n!=null){this.ft.add(i);let o=typeof n=="string"&&n.endsWith(hs);i.includes("-")||o?r.setProperty(i,o?n.slice(0,-11):n,o?ni:""):r[i]=n}}return k}});var D=ne(class extends Q{constructor(t){if(super(t),t.type!==N.PROPERTY&&t.type!==N.ATTRIBUTE&&t.type!==N.BOOLEAN_ATTRIBUTE)throw Error("The `live` directive is not allowed on child or event bindings");if(!ti(t))throw Error("`live` bindings can only contain a single expression")}render(t){return t}update(t,[e]){if(e===k||e===u)return e;let r=t.element,i=t.name;if(t.type===N.PROPERTY){if(e===r[i])return k}else if(t.type===N.BOOLEAN_ATTRIBUTE){if(!!e===r.hasAttribute(i))return k}else if(t.type===N.ATTRIBUTE&&r.getAttribute(i)===e+"")return k;return ct(t),e}});var Gt="parcels";function te(t,e,r){return t.callService(Gt,e,r,void 0,!1)}async function si(t,e,r){let n=(await t.callService(Gt,e,r,void 0,!1,!0))?.response;if(typeof n!="object"||n===null)return null;let o=n.parcel_id;return typeof o=="string"&&o!==""?o:null}function j(t,e,r={}){return t.callWS({...r,type:`${Gt}/${e}`})}var oe={amazon:"Amazon Logistics",asendia:"Asendia",bpost:"bpost",brt:"BRT",cainiao:"Cainiao",chronopost:"Chronopost",colissimo:"Colissimo",correos:"Correos",correos_express:"Correos Express",ctt:"CTT",ctt_expresso:"CTT Expresso",deutsche_post:"Deutsche Post",dhl:"DHL",dpd:"DPD",evri:"Evri",fedex:"FedEx",gls:"GLS",hermes:"Hermes",inpost:"InPost",la_poste:"La Poste",mondial_relay:"Mondial Relay",mrw:"MRW",nacex:"Nacex",paack:"Paack",postnl:"PostNL",poste_italiane:"Poste Italiane",royal_mail:"Royal Mail",sda:"SDA",seur:"SEUR",tnt:"TNT",ups:"UPS",usps:"USPS",vinted_go:"Vinted Go",yunexpress:"YunExpress",other:"Other"};function ut(){return Object.entries(oe).filter(([t])=>t!=="other").map(([t,e])=>({id:t,name:e})).sort((t,e)=>t.name.localeCompare(e.name,"en",{sensitivity:"base"})).concat([{id:"other",name:oe.other??"Other"}])}function oi(t){return Object.hasOwn(oe,t)?oe[t]??t:t}var s={weekCardName:"Parcels week",weekCardDescription:"A Monday to Sunday calendar of your parcel deliveries.",listCardName:"Parcels without a date",listCardDescription:"Active parcels that don't have a delivery date yet.",reviewCardName:"Parcels review",reviewCardDescription:"E-mails that need a decision before Parcels uses them. Only shown to administrators.",defaultWeekTitle:"Parcels",defaultListTitle:"No date yet",defaultReviewTitle:"Parcels review",loading:"Loading parcels\u2026",loadError:"Couldn't load parcels: {message}",refreshError:"Couldn't update parcels: {message}",unknownError:"Unknown error",close:"Close",cancel:"Cancel",save:"Save",dismissMessage:"Dismiss message",configInvalid:"Invalid configuration: expected a map of options.",configTitle:'Invalid configuration: "title" must be text.',configShowArchived:'Invalid configuration: "show_archived" must be true or false.',previousWeek:"Previous week",nextWeek:"Next week",today:"Today",goToToday:"Go to the current week",weekNavigation:"Week navigation",weekOf:"Week of {range}",refresh:"Check mailboxes now",refreshFailed:"Couldn't check the mailboxes: {message}",addParcel:"Add parcel",noDeliveriesThisWeek:"No deliveries this week",noDeliveriesThisDay:"No deliveries",filterLabel:"Show parcels",filterAll:"All",filterActive:"Active",filterRecent:"Recent",filterRecentHint:"Changed or expected this week",filterCompleted:"Completed",filterEmptyWeek:"Nothing to show this week with this filter",filterNote:"Filter: {filter}",filterShowAll:"Show all",todayTag:"Today",privateParcel:"Private parcel",unnamedParcel:"Parcel",packages:"{count} packages",carrierNotKnown:"Carrier not known yet",carrierNotKnownLabel:"carrier not known yet",carrierIs:"carrier {carrier}",hasCode:"PIN in the details",pin:"PIN {code}",unknownSeller:"Unknown seller",itemsCount:"{count} items",itemsNotKnown:"Items not known yet",possibly:"Possibly: {items}",possiblyOr:" or ",itemsMore:"{name} +{count}",possibleMatches:"Possibly the same package as",possibleHintOrderMany:"Not confirmed: the carrier's e-mails for these deliveries don't name an order. Merge the one this package came in, or rule out the others.",possibleHintOrderOne:"Not confirmed: the carrier's e-mails for this delivery don't name an order. Merge it if this package came in it, or rule it out.",possibleHintDeliveryMany:"Not confirmed: the carrier's e-mails for this delivery don't name an order. Merge the order that came in it, or rule out the others.",possibleHintDeliveryOne:"Not confirmed: the carrier's e-mails for this delivery don't name an order. Merge the order if it came in it, or rule it out.",possibleHintStemMany:"Not confirmed: this parcel's e-mails name only a shipment that several packages share. Merge the package they're about, or rule out the others.",possibleHintStemOne:"Not confirmed: this parcel's e-mails name only a shipment reference. Merge the package if they're about it, or rule it out.",possibleHintShipment:"Not confirmed: an e-mail names only the shipment this package is part of. Merge it if it's about this package, or rule it out.",candidateEmail:"1 e-mail from {name}",candidateEmails:"{count} e-mails from {name}",candidateUpdate:"1 update from {name}",candidateUpdates:"{count} updates from {name}",candidateMore:"+{count} more",carrierEmailsNoItems:"Carrier e-mails don't list items",trackingNoItems:"Tracking updates don't list items",couldAlsoBe:"Could also be: {list}",couldAlsoBeOrder:"{items} (order {tail})",notThisOne:"Not this one",notThisOneLabel:"{candidate} isn't {title}",aiBadge:"AI",aiBadgeLabel:"found by the local AI",aiFilledLabel:"details filled in by the local AI",privateLabel:"private",autoMerged:"Auto-merged \u2014 check",autoMergedLabel:"merged automatically, please check",undo:"Undo",undoMergeLabel:"Undo the automatic merge of {title}",undoFailed:"Couldn't undo the merge: {message}",keep:"Keep",keepMergeLabel:"Keep the automatic merge of {title}",keepFailed:"Couldn't keep the merge: {message}",inferred:"Delivery inferred \u2014 check",inferredLabel:"delivery inferred, please check",undoInferredLabel:"Undo the inferred delivery of {title}",undoInferredFailed:"Couldn't undo the delivery: {message}",keepInferredLabel:"Keep the inferred delivery of {title}",keepInferredFailed:"Couldn't keep the delivery: {message}",continuesBefore:"started before this week",continuesAfter:"continues after this week",deliveredOn:"delivered {date}",returnedOn:"returned {date}",expectedOn:"expected {date}",readyForPickupSince:"ready for pickup since {date}",statusOn:"{status} on {date}",windowFrom:"from {time}",windowUntil:"until {time}",noUndatedParcels:"Every active parcel has a delivery date.",noUndatedMatch:"No parcels without a date match this filter.",tabReview:"Needs review",tabFiltered:"Filtered",tabCount:"{label} ({count})",possibleDuplicate:"Possible duplicate",suggestionTitle:"Same parcel as {parcel}?",suggestionHint:"Merge the parcel that is the same one, or keep them apart.",reasonIs:"Reason: {reason}",mergeSuggested:"Merge",mergeSuggestedLabel:"Merge {candidate} into {title}",keepApart:"Keep apart",keepApartLabel:"Keep {title} apart from these parcels",reviewTabs:"Review lists",emptyReview:"Nothing to review.",emptyFiltered:"No filtered e-mails.",filteredHint:"E-mails the local AI classed as not about a parcel, and e-mails removed from a parcel in its details. Restore reads one again.",receivedOn:"Received {date}",noSubject:"(no subject)",mailboxOf:"Mailbox: {owner}",unverifiedSender:"Unverified sender",unverifiedSenderHint:"This e-mail didn't pass the sender checks (DKIM/DMARC). Make sure it's genuine before you accept it.",aiSuggestionLabel:"read by the local AI",suggestion:"Suggestion",noSuggestion:"No suggestion. Use Edit to enter the details yourself.",accept:"Accept",acceptWithChanges:"Accept with changes",edit:"Edit",dismiss:"Dismiss",trustSender:"Trust this sender",trustSenderHint:"Treat e-mails from {domain} as a known sender from now on",trustQuestion:"Trust {domain}? This e-mail failed the sender checks, and anyone can send e-mail that claims to come from {domain}. Its e-mails waiting here will be added as they are.",trustConfirm:"Trust {domain}",trustedSenderNote:"You trust {domain}, but this e-mail failed the sender checks. Make sure it's genuine before you accept it.",trustDone:"Trusted {domain}.",trustDoneWith:"Trusted {domain}: {parts}.",trustAddedOne:"added 1 e-mail",trustAddedMany:"added {count} e-mails",trustRecheckOne:"reading 1 e-mail again",trustRecheckMany:"reading {count} e-mails again",trustKeptOne:"1 still needs review",trustKeptMany:"{count} still need review",senderChecks:"Sender check details",failedChecks:"Checks the AI answer failed",aiNotes:"Notes on the AI answer",aiNotesHint:"What Parcels changed in the answer while checking it. These aren't failed checks.",checkHeaders:"Authentication headers",checkServers:"Servers, in order",checkNoServer:"(no name)",checkOriginals:"Renamed by the mail provider",checkUsed:"Header used",checkUsedNone:"None",checkUsedHeader:"Header {n}",checkNoResult:"none",ignoreSender:"Ignore this sender",ignoreSenderHint:"Skip e-mails from {domain} from now on",restore:"Restore",clear:"Clear",clearHint:"Remove this e-mail from the list. It won't be read again.",clearAll:"Clear all",clearAllQuestion:"Clear all filtered e-mails? They won't be read again.",aiQueueOne:"1 e-mail waiting for the local AI",aiQueueMany:"{count} e-mails waiting for the local AI",aiQueueMinutes:"{queue}, about {minutes} min",aiQueueHours:"{queue}, about {hours} h",fieldKind:"Type",fieldMerchant:"Merchant",fieldCarrier:"Carrier",fieldTrackingNumber:"Tracking number",fieldTrackingNumbers:"Tracking numbers",fieldOrderNumbers:"Order numbers",fieldReference:"Shipment reference",fieldEtaStart:"Expected from",fieldEtaEnd:"Expected until",fieldWindowStart:"Time window from",fieldWindowEnd:"Time window until",fieldPickupPoint:"Pickup point",fieldPickupCode:"PIN or pickup code",fieldItems:"Items",fieldPrivate:"Private (only the owners can see it)",hintList:"Separate with commas or new lines.",hintItems:"One per line.",carrierAuto:"Detect automatically",carrierUnknown:"Unknown",details:"Parcel details",status:"Status",sinceDate:"since {date}",dateNotKnown:"Date not known",dateNotKnownInline:"date not known",carrier:"Delivered by",notKnownYet:"Not known yet",trackOnline:"Track on the carrier's site",opensInNewTab:"(opens in a new tab)",trackingNumber:"Tracking number",copy:"Copy",copyTrackingNumber:"Copy the tracking number",copied:"Copied.",copyFailed:"Couldn't copy automatically. The number is selected, so you can copy it yourself.",merchant:"Merchant",seller:"Sold by",parcelAppName:"Name in the Parcel app",orders:"Orders",references:"Shipment reference",items:"Items",expected:"Expected",timeWindow:"Time window",pickupPoint:"Pickup point",pickupCode:"PIN or pickup code",packagesInShipment:"Packages",showPackage:"Show package {name}",showParcel:"Show parcel {name}",parcelId:"Parcel ID",delivered:"Delivered",timeline:"Timeline",noTimeline:"No events yet.",provisional:"Provisional",provisionalHint:"Made from an order e-mail. It's completed when the shipping e-mail arrives.",archived:"Archived",private:"Private",loadingDetails:"Loading details\u2026",detailsError:"Couldn't load the details: {message}",retry:"Try again",notFound:"This parcel no longer exists.",aiNotice:"Found by the local AI. Check the details, then confirm them.",aiFilledNotice:"Some details were filled in by the local AI. Check them, then confirm.",confirm:"Confirm",confirmLabel:"Confirm the details the local AI found",confirmFilledLabel:"Confirm the details the local AI filled in",mergedNotice:"Merged automatically ({reason}). Check that it's one parcel.",mergedNoticeNoReason:"Merged automatically. Check that it's one parcel.",inferredNotice:"Probably delivered: another parcel from this shop was delivered around the expected day. Undo if it hasn't arrived.",inferredQuietNotice:"Probably delivered: no news for three weeks. Undo if it hasn't arrived.",markDelivered:"Mark delivered",editDate:"Edit date",checkAgain:"Check again",checkingAgain:"Checking\u2026",checkAgainHint:"Read this parcel's e-mails again, and let the local AI look for what's missing",checkAgainReadOne:"Read 1 e-mail again.",checkAgainReadMany:"Read {count} e-mails again.",checkAgainGoneOne:"1 e-mail is no longer in the mailbox.",checkAgainGoneMany:"{count} e-mails are no longer in the mailbox.",checkAgainFailedOne:"1 e-mail couldn't be downloaded; try again later.",checkAgainFailedMany:"{count} e-mails couldn't be downloaded; try again later.",checkAgainNoEmails:"This parcel has no e-mails to read again.",checkAgainQueuedOne:"The local AI is checking 1 e-mail.",checkAgainQueuedMany:"The local AI is checking {count} e-mails.",checkAgainSuggest:"What it finds waits under Needs review.",checkAgainAuto:"What it finds is added to this parcel.",checkAgainNothingForAi:"There was nothing for the local AI to fill in.",checkAgainAiOff:"The local AI is off.",mergeWith:"Merge with\u2026",split:"Split\u2026",archive:"Archive",actions:"Actions",mergeIntro:"Choose the parcel to merge into this one. Likely matches come first.",mergeChoose:"Parcel",mergeConfirm:"Merge",mergeChooseFirst:"Choose a parcel first.",mergeSearch:"Search",mergeSearchPlaceholder:"Shop, item, order, number or carrier",mergeShowOlder:"Show older ({count})",mergeNoMatch:"No parcel matches the search.",noMergeCandidates:"There are no other parcels to merge with.",numberTail:"No. {tail}",orderTail:"Order {tail}",splitIntro:"Choose what to move to a new parcel.",splitConfirm:"Split off",splitHint:"Choose at least one, but not all of them.",archiveQuestion:"Archive this parcel? It no longer counts as active.",dateEndBeforeStart:"The end date is before the start date.",dateEndWithoutStart:"Set a start date too.",windowEndBeforeStart:"The time window must end after it starts.",actionFailed:"That didn't work: {message}",dayAtTime:"{day} at {time}",originsTitle:"E-mails ({count})",originsAndUpdatesTitle:"E-mails and updates ({count})",originsHint:"What each e-mail and source said and added to this parcel, oldest first.",originEmail:"E-mail",originEdits:"Changed by hand",factShop:"Shop: {name}",factSeller:"Sold by {name}",factShipment:"Shipment {n}/{total}",factCarrierNumber:"{carrier} No. {tail}",factReference:"Reference {tail}",factPickup:"Pickup: {place}",factName:"Name: {name}",originItems:"Items",originAiAll:"read by the local AI",originAiPart:"partly read by the local AI",originRepeats:"{count} more from {sender}",originRepeatsLatest:"latest: {said}",moveToNewParcel:"Move to a new parcel",moveToNewParcelLabel:"Move to a new parcel: {row}",removeFromParcels:"Remove from Parcels",removeFromParcelsLabel:"Remove from Parcels: {row}",splitBlockedNothingLeft:"Can't move: nothing else would be left in this parcel.",splitBlockedShared:"Can't move: it shares the tracking number or shipment with other e-mails here.",splitBlockedOther:"Can't move this one to a new parcel.",movedNotice:"Moved to a new parcel.",movedBackNotice:"Moved back into this parcel.",removedNotice:"Removed from Parcels. It's listed under Filtered in Needs review.",removedGoneNotice:"Removed from Parcels. Nothing else was left in this parcel, so it's gone. Undo reads the e-mail again.",restoredNotice:"Restored. The e-mail was read again.",restoredElsewhereNotice:"Restored. The e-mail was read again into another parcel.",restoredReviewNotice:"Restored. The e-mail is no longer in the mailbox, so it waits under Needs review.",restoredNoParcelNotice:"Restored. The e-mail was read again, but it isn't part of a parcel now. Look under Needs review.",showOtherParcel:"Show",showOtherParcelLabel:"Show that parcel",removedFromParcel:"Removed from a parcel",addTitle:"Add parcel",addSubmit:"Add",trackingRequired:"Enter a tracking number.",returnBadge:"Return",privateReturn:"Private return",returnTo:"Return to {merchant}",returnPlain:"Return",returnPickup:"Return pickup",returnPickedUp:"Return picked up",returnReceived:"Received by the shop",returnStarted:"Return started",pickupOn:"pickup {date}",pickedUpOn:"picked up {date}",returnStartedOn:"started {date}",receivedByShopLabel:"received by the shop",pickupRuleEmail:"date from the e-mail",pickupRuleNextWorkingDay:"the e-mail says the next working day",pickupRuleAssumed:"usually the working day after the e-mail",returnDetails:"Return details",pickup:"Pickup",returnStartedDay:"Started",returnCarrier:"Carrier",returnSentBackFrom:"Original delivery",returnEmails:"E-mails",returnNotFound:"This return no longer exists.",returnHint:"Items you send back to a shop. Their parcel keeps its delivery; the return shows on its pickup day.",removeReturn:"Remove",removeReturnQuestion:"Remove this return? Its e-mails won't be read again, and a delivery worked out only from it is undone.",inferredReturnNotice:"Probably delivered: you're sending its items back. Undo if it hasn't arrived."},ai={ordered:"Ordered",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",exception:"Problem with delivery",ready_for_pickup:"Ready for pickup",returned:"Returned to sender",cancelled:"Cancelled"},pt={order:"Order confirmation",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",ready_for_pickup:"Ready for pickup",delayed:"Delayed",customs:"Held at customs",return:"Returned to sender",customer_return:"Return pickup",cancelled:"Cancelled",code:"Delivery code",not_parcel:"Not about a parcel",unknown:"Unknown"},li={parser:"E-mail",ai:"Local AI",manual:"Added by hand",seventeentrack:"17TRACK",parcelapp:"Parcel app",inferred:"Inferred from another delivery",inferred_return:"Inferred from a return",quiet:"No news for three weeks"},ci={unknown_sender:"Unknown sender",not_aligned:"The sender's domain isn't authenticated (DKIM/DMARC)",no_auth_header:"No authentication results in the e-mail",untrusted_authserv:"Authentication results from an unknown server",multiple_auth_results:"More than one set of authentication results, so it can't tell which is real",low_confidence:"Not sure about the details",unknown_format:"Unknown e-mail format",ai_suggestion:"Read by the local AI",ai_fill:"The local AI found details the parser missed",ai_unavailable:"The local AI wasn't available",ai_timeout:"The local AI took too long on this e-mail",ai_rejected:"The local AI's answer didn't pass the checks",restored:"Moved back from Filtered"},Vt={tracking_added_by_detector:"Parcels' own detector added a tracking number that the e-mail writes.",pickup_code_from_text:"The e-mail's only delivery or pickup code was used, as the answer gave none that the e-mail writes.",item_recommended:"Products the e-mail lists only under Buy again or Recommended for you were dropped.",item_is_number:"An item that was the parcel's tracking or order number, code or reference was dropped.",kind_from_text:"The e-mail's words give a different status from the answer's, and theirs was used.",out_for_delivery_not_today:"Out for delivery, with a later delivery date and no such words in the e-mail, was read as in transit.",eta_dropped_for_kind:"A date was dropped, as no delivery is pending in e-mails of this kind.",eta_from_text:"The date by the e-mail's delivery words was used, as the answer gave another date or none.",order_moved_to_tracking:"An order number in a carrier's e-mail was the parcel's tracking number.",order_from_text:"An order number was taken as the e-mail writes it: the whole joined number, or a miscopy repaired.",tracking_from_text:"A miscopied tracking number was replaced by the e-mail's own.",merchant_is_carrier:"The shop given was this e-mail's carrier, so it was dropped.",carrier_unproven:"The shop, such as Amazon, was given as the carrier without proof that it delivers, so the carrier was left empty.",merchant_from_sender_name:"A shop given as a domain was named from the sender's name.",merchant_from_text:"A shop given as a domain was named from a line of the e-mail.",pickup_point_not_pickup:"An address the e-mail doesn't give as a pickup point was dropped.",pickup_point_generic:"A generic pickup point, such as a branch, was dropped."},di={same_number:"same tracking number",same_merchant_eta:"same shop and delivery date",same_merchant_day:"same shop, delivered on the expected day",same_merchant_domain:"the shop's tracked shipment followed its order",same_order:"same order",same_reference:"same shipment reference"};function p(t,e){return t.replace(/\{(\w+)\}/g,(r,i)=>Object.hasOwn(e,i)?String(e[i]):r)}function q(t){if(typeof t=="string"&&t.trim())return t;if(t&&typeof t=="object"){let e=t.message;if(typeof e=="string"&&e.trim())return e;let r=t.code;if(typeof r=="string"&&r.trim())return r}return s.unknownError}var ms=["a[href]","button:not([disabled])","input:not([disabled]):not([type='hidden'])","select:not([disabled])","textarea:not([disabled])","[tabindex]:not([tabindex='-1'])"].join(",");function fs(t){return[...t.querySelectorAll(ms)].filter(e=>!e.closest("[hidden], [inert]")&&e.getClientRects().length>0)}function ui(t,e){if(t.key!=="Tab"||t.altKey||t.ctrlKey||t.metaKey)return;let r=fs(e),i=r[0],n=r[r.length-1];if(!i||!n){t.preventDefault(),e.focus();return}let a=e.getRootNode().activeElement,c=a instanceof HTMLElement&&e.contains(a)&&a!==e;t.shiftKey&&(!c||a===i)?(t.preventDefault(),n.focus()):!t.shiftKey&&(!c||a===n)&&(t.preventDefault(),i.focus())}var gs="parcels-error",pi="parcels-open-parcel",hi="parcels-open-return",ae=class extends Y{static properties={hass:{attribute:!1},_open:{state:!0},_busy:{state:!0},_error:{state:!0}};_returnFocus=null;_pressedBackdrop=!1;_hadFocus=!1;_session=0;constructor(){super(),this.hass=void 0,this._open=!1,this._busy=!1,this._error=null}render(){return l`<dialog
      aria-labelledby="dialog-title"
      @close=${this._onClose}
      @keydown=${this._onKeyDown}
      @pointerdown=${this._onPointerDown}
      @click=${this._onClick}
    >
      ${this._open?this.renderContent():u}
    </dialog>`}renderContent(){return u}canLightDismiss(){return!this._busy}dialogClosed(){}get isOpen(){return this._open}async showDialog(e){this._session+=1,this._returnFocus=e,this._open=!0,this._busy=!1,this._error=null,await this.updateComplete;let r=this._dialog();!r||!this._open||!this.isConnected||(r.open||r.showModal(),this.focusInDialog("[data-autofocus]"))}closeDialog(){let e=this._dialog();e?.open&&e.close(),this._finishClose(!0)}focusInDialog(e){this.renderRoot.querySelector(`dialog ${e}`)?.focus()}async focusAfterRender(e){await this.updateComplete,this._open&&this.focusInDialog(e)}async runAction(e,r){if(this._busy)return;let i=this._session;this._busy=!0,this._error=null;try{await e(),this._open&&this._session===i&&r?.()}catch(n){let o=p(s.actionFailed,{message:q(n)});this._open&&this._session===i?this._error=o:this.dispatchEvent(new CustomEvent(gs,{detail:o}))}finally{this._session===i&&(this._busy=!1)}}disconnectedCallback(){super.disconnectedCallback(),this._finishClose(!1)}willUpdate(e){this._hadFocus=this._open&&!!this.shadowRoot?.activeElement}updated(e){this._hadFocus&&this._open&&!this.shadowRoot?.activeElement&&this.focusInDialog("[data-autofocus]"),this._hadFocus=!1}_dialog(){return this.renderRoot.querySelector("dialog")}_finishClose(e){if(!this._open)return;let r=this._returnFocus;this._returnFocus=null,this._open=!1,this._busy=!1,this._error=null,this._pressedBackdrop=!1,this.dialogClosed(),e&&r?.()}_onClose(e){let r=e.currentTarget;e.target===r&&!r.open&&this._finishClose(!0)}_onKeyDown(e){ui(e,e.currentTarget)}_onPointerDown(e){this._pressedBackdrop=e.target===e.currentTarget}_onClick(e){let r=this._pressedBackdrop&&e.target===e.currentTarget;this._pressedBackdrop=!1,r&&this.canLightDismiss()&&this.closeDialog()}};var _s=/^(\d{4})-(\d{2})-(\d{2})$/,bs=/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)(?:[.,](\d+))?(Z|[+-]\d{2}(?::?\d{2})?)?$/i,vs=[31,28,31,30,31,30,31,31,30,31,30,31];function ys(t){return t%4===0&&t%100!==0||t%400===0}function ws(t,e){return e===2&&ys(t)?29:vs[e-1]??0}function ft(t){if(typeof t!="string")return null;let e=_s.exec(t);if(!e)return null;let r=Number(e[1]),i=Number(e[2]),n=Number(e[3]);return i<1||i>12||n<1||n>ws(r,i)?null:{year:r,month:i,day:n}}function F(t){return ft(t)!==null}function ht(t){let e=ft(t);if(!e)throw new RangeError(`Not a YYYY-MM-DD date: ${t}`);return e}function mt({year:t,month:e,day:r}){let i=e<=2?t-1:t,n=Math.floor(i/400),o=i-n*400,a=(e+9)%12,c=Math.floor((153*a+2)/5)+r-1,d=o*365+Math.floor(o/4)-Math.floor(o/100)+c;return n*146097+d-719468}function $s(t){let e=t+719468,r=Math.floor(e/146097),i=e-r*146097,n=Math.floor((i-Math.floor(i/1460)+Math.floor(i/36524)-Math.floor(i/146096))/365),o=i-(365*n+Math.floor(n/4)-Math.floor(n/100)),a=Math.floor((5*o+2)/153),c=o-Math.floor((153*a+2)/5)+1,d=a<10?a+3:a-9;return{year:n+r*400+(d<=2?1:0),month:d,day:c}}function ks({year:t,month:e,day:r}){return`${String(t).padStart(4,"0")}-${String(e).padStart(2,"0")}-${String(r).padStart(2,"0")}`}function re(t,e){return ks($s(mt(ht(t))+e))}function le(t,e){return mt(ht(e))-mt(ht(t))}function xs(t){return((mt(ht(t))+3)%7+7)%7}function ze(t){return re(t,-xs(t))}function fi(t){return Array.from({length:7},(e,r)=>re(t,r))}function $(t,e){return t<e?-1:t>e?1:0}function gi(t,e){return $(t,e)>=0?t:e}function L(t){if(typeof t!="string")return null;let e=bs.exec(t.trim());if(!e)return null;let[,r,i,n,o]=e;if(!r||!i||!F(r))return null;let a=n?`.${n.slice(0,3).padEnd(3,"0")}`:"",c="Z";if(o&&o.toUpperCase()!=="Z"){let m=o.slice(1).replace(":","").padEnd(4,"0");c=`${o[0]}${m.slice(0,2)}:${m.slice(2,4)}`}let d=Date.parse(`${r}T${i}${a}${c}`);return Number.isNaN(d)?null:d}var mi=new Map;function Ss(t){let e=mi.get(t);if(!e){let r={calendar:"gregory",numberingSystem:"latn",year:"numeric",month:"2-digit",day:"2-digit"};try{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:t})}catch{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:"UTC"})}mi.set(t,e)}return e}function E(t,e){if(F(t))return t;let r=L(t);if(r===null)return null;let i="",n="",o="";for(let c of Ss(e).formatToParts(r))c.type==="year"?i=c.value:c.type==="month"?n=c.value:c.type==="day"&&(o=c.value);let a=`${i.padStart(4,"0")}-${n}-${o}`;return F(a)?a:null}function Rs(t){return[...new Set(t)]}function _i(t){return Rs(t.split(/[\n,;]+/).map(e=>e.trim()).filter(Boolean))}function Ts(t){return t.split(/\r?\n/).map(e=>e.trim()).filter(Boolean)}function Z(t){let e=/^(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?$/.exec((t??"").trim());if(!e)return null;let r=Number(e[1]),i=Number(e[2]);return r>23||i>59?null:`${String(r).padStart(2,"0")}:${String(i).padStart(2,"0")}`}function G(t){let e=t.trim();return e||null}function Cs(t,e){return e&&!t?s.dateEndWithoutStart:t&&e&&$(e,t)<0?s.dateEndBeforeStart:null}function As(t,e){let r=Z(t),i=Z(e);return r&&i&&i<=r?s.windowEndBeforeStart:null}function bi(t){return{eta_start:t.eta_start??"",eta_end:t.eta_end??"",window_start:Z(t.window_start)??"",window_end:Z(t.window_end)??""}}function gt(t){let e=Cs(t.eta_start,t.eta_end);if(e)return{message:e,field:e===s.dateEndWithoutStart?"eta_start":"eta_end"};let r=As(t.window_start,t.window_end);return r?{message:r,field:"window_end"}:null}function vi(t,e){return{parcel_id:t,eta_start:G(e.eta_start),eta_end:G(e.eta_end),window_start:Z(e.window_start),window_end:Z(e.window_end)}}var yi="shipped";function Yt(t){return{kind:t?.kind||yi,merchant:t?.merchant??"",carrier:t?.carrier??"",tracking_numbers:(t?.tracking_numbers??[]).join(", "),order_numbers:(t?.order_numbers??[]).join(", "),eta_start:t?.eta_start??"",eta_end:t?.eta_end??"",window_start:Z(t?.window_start)??"",window_end:Z(t?.window_end)??"",pickup_point:t?.pickup_point??"",pickup_code:t?.pickup_code??"",items:(t?.items??[]).join(`
`),reference:t?.reference??""}}function wi(t){return{kind:t.kind.trim()||yi,merchant:G(t.merchant),carrier:G(t.carrier),tracking_numbers:_i(t.tracking_numbers),order_numbers:_i(t.order_numbers),eta_start:G(t.eta_start),eta_end:G(t.eta_end),window_start:Z(t.window_start),window_end:Z(t.window_end),pickup_point:G(t.pickup_point),pickup_code:G(t.pickup_code),items:Ts(t.items),reference:G(t.reference)}}function $i(t){let e=t.tracking_number.trim();if(!e)return null;let r={tracking_number:e},i=G(t.carrier);i&&(r.carrier=i);let n=G(t.merchant);return n&&(r.merchant=n),t.private&&(r.private=!0),r}function Qt(t,e){return t.length>0&&t.length<e}var Es="https://github.com/fratei/ha-parcels";function K(t,e){customElements.get(t)||customElements.define(t,e)}function Te(t,e,r){let i=window;Array.isArray(i.customCards)||(i.customCards=[]);let n=i.customCards;n.some(o=>o?.type===t)||n.push({type:t,name:e,description:r,preview:!0,documentationURL:Es})}var W=R`
  :host {
    display: block;
    color: var(--primary-text-color, #212121);
  }
  :host([hidden]),
  [hidden] {
    display: none !important;
  }
  :host([dark]) {
    color-scheme: dark;
  }
  :host(:dir(rtl)) .flip {
    transform: scaleX(-1);
  }

  .header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 12px;
    padding: 12px 16px 8px;
  }
  .title {
    flex: 1 1 auto;
    min-width: 0;
    margin: 0;
    font-size: var(--ha-card-header-font-size, 1.25rem);
    font-weight: 500;
    line-height: 1.3;
    overflow-wrap: anywhere;
  }
  .content {
    padding: 0 16px 16px;
  }
  .header + .content {
    padding-top: 4px;
  }
  .content:first-child {
    padding-top: 16px;
  }

  button {
    font: inherit;
    color: inherit;
  }
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    box-sizing: border-box;
    min-height: 36px;
    padding: 0 14px;
    border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
    border-radius: 18px;
    background: transparent;
    color: var(--primary-color, #03a9f4);
    font-size: 0.875rem;
    font-weight: 500;
    line-height: 1.2;
    cursor: pointer;
    --mdc-icon-size: 18px;
  }
  .btn:hover:not(:disabled, [aria-disabled="true"]) {
    background: color-mix(in srgb, var(--primary-color, #03a9f4) 8%, transparent);
  }
  .btn.primary {
    border-color: transparent;
    background: var(--primary-color, #03a9f4);
    color: var(--text-primary-color, #fff);
  }
  .btn.primary:hover:not(:disabled, [aria-disabled="true"]) {
    background: color-mix(in srgb, var(--primary-color, #03a9f4) 85%, #000);
  }
  .btn.danger {
    color: var(--error-color, #db4437);
  }
  .btn.danger.primary {
    background: var(--error-color, #db4437);
    color: var(--text-primary-color, #fff);
  }
  .icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: none;
    width: 36px;
    height: 36px;
    padding: 0;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: var(--secondary-text-color, #727272);
    cursor: pointer;
    --mdc-icon-size: 20px;
  }
  .icon-btn:hover:not(:disabled, [aria-disabled="true"]) {
    background: color-mix(in srgb, currentColor 12%, transparent);
  }
  .link-btn {
    min-height: 24px;
    padding: 2px 4px;
    border: none;
    border-radius: 4px;
    background: none;
    color: var(--primary-color, #03a9f4);
    font-size: inherit;
    font-weight: 500;
    text-decoration: underline;
    cursor: pointer;
  }
  .btn:disabled,
  .icon-btn:disabled,
  .link-btn:disabled,
  [aria-disabled="true"] {
    opacity: 0.5;
    cursor: default;
  }
  a {
    color: var(--primary-color, #03a9f4);
  }
  :is(button, a, input, select, textarea, [tabindex]):focus-visible {
    outline: 2px solid var(--primary-color, #03a9f4);
    outline-offset: 2px;
  }

  input:not([type="checkbox"]),
  select,
  textarea {
    box-sizing: border-box;
    width: 100%;
    min-height: 40px;
    padding: 8px 10px;
    border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
    border-radius: 8px;
    background: var(--card-background-color, var(--ha-card-background, #fff));
    color: var(--primary-text-color, #212121);
    font: inherit;
  }
  textarea {
    min-height: 80px;
    resize: vertical;
  }
  input[type="checkbox"] {
    flex: none;
    width: 18px;
    height: 18px;
    margin: 0;
    accent-color: var(--primary-color, #03a9f4);
  }
  [aria-invalid="true"] {
    border-color: var(--error-color, #db4437) !important;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }
  .field-label {
    font-size: 0.875rem;
    color: var(--secondary-text-color, #727272);
  }
  .hint {
    margin: 0;
    font-size: 0.8125rem;
    color: var(--secondary-text-color, #727272);
  }
  .check-row {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 36px;
    cursor: pointer;
  }
  .form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
    gap: 12px;
  }
  .form-grid .wide {
    grid-column: 1 / -1;
  }
  .row-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
  }

  .badge {
    --badge-color: var(--secondary-text-color, #727272);
    display: inline-flex;
    flex: none;
    align-items: center;
    gap: 2px;
    box-sizing: border-box;
    min-height: 18px;
    padding: 0 6px;
    border: 1px solid color-mix(in srgb, var(--badge-color) 55%, transparent);
    border-radius: 9px;
    background: color-mix(in srgb, var(--badge-color) 18%, transparent);
    color: var(--primary-text-color, #212121);
    font-size: 0.6875rem;
    font-weight: 600;
    line-height: 16px;
    white-space: nowrap;
    --mdc-icon-size: 14px;
  }
  .badge.ai {
    --badge-color: var(--purple-color, #926bc7);
  }
  .badge.warning {
    --badge-color: var(--warning-color, #ffa600);
  }
  .badge.info {
    --badge-color: var(--info-color, #039be5);
  }
  /* The returns colour (RETURN_COLOR in returns.ts). */
  .badge.return {
    --badge-color: var(--pink-color, #e91e63);
  }

  .alert {
    --alert-color: var(--info-color, #039be5);
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin: 8px 0;
    padding: 8px 12px;
    border-inline-start: 4px solid var(--alert-color);
    border-radius: 8px;
    background: color-mix(in srgb, var(--alert-color) 12%, transparent);
    font-size: 0.875rem;
    overflow-wrap: anywhere;
    --mdc-icon-size: 20px;
  }
  .alert.error {
    --alert-color: var(--error-color, #db4437);
  }
  .alert.warning {
    --alert-color: var(--warning-color, #ffa600);
  }
  .alert .grow {
    flex: 1 1 auto;
    min-width: 0;
    align-self: center;
  }
  .alert .btn {
    flex: none;
    overflow-wrap: normal;
  }
  .alert .icon-btn {
    width: 28px;
    height: 28px;
    margin: -4px -6px -4px 0;
  }
  .banners {
    padding: 0 16px;
  }
  .banners:first-child {
    padding-top: 16px;
  }
  .banners .alert {
    margin: 0 0 8px;
  }
  .muted {
    color: var(--secondary-text-color, #727272);
  }
  .empty {
    margin: 0;
    padding: 12px 0;
    color: var(--secondary-text-color, #727272);
    text-align: center;
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }
`,_t=R`
  .chip {
    --chip-color: var(--secondary-text-color, #727272);
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    min-width: 0;
    border-inline-start: 4px solid var(--chip-color);
    border-radius: 8px;
    overflow: hidden;
    background: var(--secondary-background-color, #f2f2f2);
    background: color-mix(
      in srgb,
      var(--chip-color) 14%,
      var(--card-background-color, var(--ha-card-background, #fff))
    );
    color: var(--primary-text-color, #212121);
  }
  .chip.cont-before {
    border-start-start-radius: 0;
    border-end-start-radius: 0;
  }
  .chip.cont-after {
    border-start-end-radius: 0;
    border-end-end-radius: 0;
  }
  .chip.returned {
    border-inline-start-style: dashed;
    background: transparent;
    outline: 1px dashed var(--divider-color, rgba(0, 0, 0, 0.12));
    outline-offset: -1px;
  }
  .chip.returned .chip-title {
    color: var(--secondary-text-color, #727272);
    font-weight: 400;
  }
  /* A customer return: its icon says so without the colour; faded once done. */
  .chip.return .ret-icon {
    flex: none;
    color: var(--chip-color);
    --mdc-icon-size: 20px;
  }
  .chip.return.done {
    background: color-mix(
      in srgb,
      var(--chip-color) 6%,
      var(--card-background-color, var(--ha-card-background, #fff))
    );
  }
  .chip-main {
    display: flex;
    align-items: center;
    box-sizing: border-box;
    width: 100%;
    min-width: 0;
    min-height: 40px;
    margin: 0;
    padding: 4px 8px;
    border: none;
    border-radius: 0;
    background: none;
    color: inherit;
    font: inherit;
    text-align: start;
  }
  button.chip-main {
    cursor: pointer;
  }
  button.chip-main:focus-visible {
    outline-offset: -2px;
  }
  button.chip-main:hover {
    background: color-mix(in srgb, var(--chip-color) 12%, transparent);
  }
  .chip-row {
    display: flex;
    flex: 1 1 auto;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }
  .chip-text {
    display: flex;
    flex: 1 1 auto;
    flex-direction: column;
    min-width: 0;
  }
  .chip-title,
  .chip-meta,
  .chip-items {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .chip-title {
    font-size: 0.875rem;
    font-weight: 500;
    line-height: 1.3;
  }
  .chip-line {
    display: flex;
    align-items: baseline;
    gap: 6px;
    min-width: 0;
  }
  .chip-meta {
    flex: 1 1 auto;
    min-width: 0;
    font-size: 0.75rem;
    line-height: 1.3;
    color: var(--secondary-text-color, #727272);
  }
  .chip-pin {
    flex: none;
    font-size: 0.75rem;
    font-weight: 600;
    line-height: 1.3;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .chip-items {
    font-size: 0.75rem;
    line-height: 1.3;
  }
  .chip-title.unknown,
  .chip-items.unknown {
    color: var(--secondary-text-color, #727272);
    font-style: italic;
    font-weight: 400;
  }
  .chip-items.possibly {
    font-style: italic;
  }
  .cont {
    flex: none;
    color: var(--chip-color);
    font-weight: 700;
  }
  .check {
    flex: none;
    color: var(--success-color, #43a047);
    font-weight: 700;
  }
  .lock {
    flex: none;
    color: var(--secondary-text-color, #727272);
    --mdc-icon-size: 16px;
  }
  .merge-note {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 2px 4px;
    padding: 0 8px 4px;
    font-size: 0.75rem;
    --mdc-icon-size: 14px;
  }
  .merge-note ha-icon {
    color: var(--warning-color, #ffa600);
  }
  .merge-note .merge-label {
    flex: 1 1 auto;
    font-weight: 500;
  }
  .merge-note .merge-detail {
    color: var(--secondary-text-color, #727272);
    font-weight: 400;
    overflow-wrap: anywhere;
  }
`,Ce=R`
  dialog {
    /* The screen edges the device keeps for itself (status bar, notch, home
       indicator): Home Assistant's values, which its apps set, else the browser's. */
    --parcels-inset-top: var(--safe-area-inset-top, env(safe-area-inset-top, 0px));
    --parcels-inset-right: var(--safe-area-inset-right, env(safe-area-inset-right, 0px));
    --parcels-inset-bottom: var(--safe-area-inset-bottom, env(safe-area-inset-bottom, 0px));
    --parcels-inset-left: var(--safe-area-inset-left, env(safe-area-inset-left, 0px));
    box-sizing: border-box;
    width: min(560px, calc(100vw - 32px - var(--parcels-inset-left) - var(--parcels-inset-right)));
    max-width: none;
    max-height: calc(100vh - 32px - var(--parcels-inset-top) - var(--parcels-inset-bottom));
    max-height: calc(100dvh - 32px - var(--parcels-inset-top) - var(--parcels-inset-bottom));
    padding: 0;
    border: none;
    border-radius: 16px;
    background: var(--ha-dialog-surface-background, var(--mdc-theme-surface, var(--card-background-color, #fff)));
    color: var(--primary-text-color, #212121);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  }
  dialog[open] {
    display: flex;
    flex-direction: column;
  }
  dialog::backdrop {
    background: rgba(0, 0, 0, 0.45);
  }
  .dialog-header {
    display: flex;
    flex: none;
    align-items: flex-start;
    gap: 8px;
    padding: 16px 12px 8px 24px;
  }
  .dialog-heading {
    flex: 1 1 auto;
    min-width: 0;
  }
  .dialog-title {
    margin: 6px 0 0;
    font-size: 1.25rem;
    font-weight: 500;
    line-height: 1.3;
    overflow-wrap: anywhere;
  }
  .dialog-badges {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    margin-top: 6px;
  }
  .dialog-content {
    flex: 1 1 auto;
    min-height: 0;
    padding: 0 24px 16px;
    overflow: auto;
    overscroll-behavior: contain;
  }
  .dialog-actions {
    display: flex;
    flex: none;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 8px;
    padding: 12px 24px 20px;
    border-top: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
  }
  .dialog-actions .spacer {
    flex: 1 1 auto;
  }
  .dialog-error,
  .dialog-status {
    flex: none;
    padding: 0 24px;
  }
  .dialog-error .alert,
  .dialog-status .alert {
    margin: 0 0 12px;
  }
  .section-title {
    margin: 16px 0 8px;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--secondary-text-color, #727272);
  }
  /* Full screen on phones, held clear of the edges the device keeps, so that the
     header with the close button and the actions can always be reached. */
  @media (max-width: 600px), (max-height: 500px) {
    dialog {
      width: 100vw;
      height: 100vh;
      height: 100dvh;
      max-height: none;
      margin: 0;
      padding-top: var(--parcels-inset-top);
      padding-right: var(--parcels-inset-right);
      padding-bottom: var(--parcels-inset-bottom);
      padding-left: var(--parcels-inset-left);
      border-radius: 0;
    }
    .dialog-header {
      padding-left: 16px;
    }
    .dialog-content {
      padding: 0 16px 16px;
    }
    .dialog-actions {
      padding: 12px 16px 16px;
    }
    .dialog-error,
    .dialog-status {
      padding: 0 16px;
    }
  }
`;var ki={tracking_number:"",carrier:"",merchant:"",private:!1},Zt=class extends ae{static properties={_form:{state:!0},_missingNumber:{state:!0}};static styles=[W,Ce,R`
      form {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding-top: 8px;
      }
      #tracking-number {
        font-family: var(--code-font-family, monospace);
      }
      .field-error {
        margin: 0;
        font-size: 0.8125rem;
        color: var(--error-color, #db4437);
      }
    `];constructor(){super(),this._form=ki,this._missingNumber=!1}async open(e=null){this._form=ki,this._missingNumber=!1,await this.showDialog(e)}canLightDismiss(){return!1}renderContent(){let e=this._form,r=this._missingNumber;return l`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">${s.addTitle}</h2>
        </div>
        <button
          type="button"
          class="icon-btn"
          aria-label=${s.close}
          title=${s.close}
          @click=${this.closeDialog}
        >
          <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
        </button>
      </div>
      <div class="dialog-content">
        <form id="add-form" novalidate @submit=${this._submit}>
          <label class="field">
            <span class="field-label">${s.fieldTrackingNumber}</span>
            <input
              id="tracking-number"
              name="tracking_number"
              required
              autocomplete="off"
              autocapitalize="characters"
              spellcheck="false"
              data-autofocus
              .value=${D(e.tracking_number)}
              aria-invalid=${r?"true":"false"}
              aria-describedby=${r?"tracking-error":u}
              @input=${this._onInput}
            />
          </label>
          ${r?l`<p class="field-error" id="tracking-error">${s.trackingRequired}</p>`:u}
          <label class="field">
            <span class="field-label">${s.fieldCarrier}</span>
            <select name="carrier" @change=${this._onInput}>
              <option value="" ?selected=${e.carrier===""}>${s.carrierAuto}</option>
              ${ut().map(i=>l`<option value=${i.id} ?selected=${e.carrier===i.id}>
                    ${i.name}
                  </option>`)}
            </select>
          </label>
          <label class="field">
            <span class="field-label">${s.fieldMerchant}</span>
            <input
              name="merchant"
              autocomplete="off"
              .value=${D(e.merchant)}
              @input=${this._onInput}
            />
          </label>
          <label class="check-row">
            <input
              type="checkbox"
              name="private"
              .checked=${D(e.private)}
              @change=${this._onInput}
            />
            <span>${s.fieldPrivate}</span>
          </label>
        </form>
      </div>
      ${this._error?l`<div class="dialog-error">
            <div class="alert error" role="alert">
              <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
              <span class="grow">${this._error}</span>
            </div>
          </div>`:u}
      <div class="dialog-actions">
        <button type="button" class="btn" @click=${this.closeDialog}>${s.cancel}</button>
        <button
          type="submit"
          form="add-form"
          class="btn primary"
          aria-disabled=${this._busy?"true":"false"}
        >
          ${s.addSubmit}
        </button>
      </div>
    `}_onInput(e){let r=e.currentTarget,i=r.name,n=r instanceof HTMLInputElement&&r.type==="checkbox"?r.checked:r.value;this._form={...this._form,[i]:n},i==="tracking_number"&&this._missingNumber&&r.value.trim()&&(this._missingNumber=!1)}_submit(e){e.preventDefault();let r=this.hass;if(!r||this._busy)return;let i=$i(this._form);if(!i){this._missingNumber=!0,this.focusAfterRender("#tracking-number");return}this.runAction(()=>te(r,"add",i),()=>this.closeDialog())}};K("parcels-add-dialog",Zt);var be=ne(class extends Q{constructor(t){if(super(t),t.type!==N.ATTRIBUTE||t.name!=="class"||t.strings?.length>2)throw Error("`classMap()` can only be used in the `class` attribute and must be the only part in the attribute.")}render(t){return" "+Object.keys(t).filter(e=>t[e]).join(" ")+" "}update(t,[e]){if(this.st===void 0){this.st=new Set,t.strings!==void 0&&(this.nt=new Set(t.strings.join(" ").split(/\s/).filter(i=>i!=="")));for(let i in e)e[i]&&!this.nt?.has(i)&&this.st.add(i);return this.render(e)}let r=t.element.classList;for(let i of this.st)i in e||(r.remove(i),this.st.delete(i));for(let i in e){let n=!!e[i];n===this.st.has(i)||this.nt?.has(i)||(n?(r.add(i),this.st.add(i)):(r.remove(i),this.st.delete(i)))}return k}});function Ps(t){try{return Intl.DateTimeFormat.supportedLocalesOf([t]),t}catch{return"en"}}function Is(){let t=new Intl.DateTimeFormat(void 0,{hour:"numeric"}).resolvedOptions().hourCycle;return t==="h11"||t==="h12"}function Ae(t,e){let r=Ps(t?.locale?.language||t?.language||"en"),i=t?.locale?.time_format,n;i==="12"?n=!0:i==="24"?n=!1:i==="system"&&(n=Is());let o=t?.locale?.time_zone==="local"?void 0:e||t?.config?.time_zone||void 0;return{language:r,hour12:n,timeZone:o}}var xi=new Map;function ce(t,e,r){let i=e.hour!==void 0||e.timeStyle!==void 0,n={...e,timeZone:r?"UTC":t.timeZone};i&&t.hour12!==void 0&&(n.hour12=t.hour12);let o=JSON.stringify([t.language,n]),a=xi.get(o);if(!a){try{a=new Intl.DateTimeFormat(t.language,n)}catch{a=new Intl.DateTimeFormat(t.language,{...n,timeZone:void 0})}xi.set(o,a)}return a}function Jt(t){let e=ft(t);return e?new Date(Date.UTC(e.year,e.month-1,e.day)):null}var Xt={weekday:"short",day:"numeric",month:"short"},Si={day:"numeric",month:"short",year:"numeric"};function H(t,e,r=Xt){let i=Jt(t);return i?ce(e,r,!0).format(i):t}function O(t,e,r,i=Xt){let n=Jt(t),o=Jt(e);return!n||!o?[t,e].filter(Boolean).join(" \u2013 "):t===e?ce(r,i,!0).format(n):ce(r,i,!0).formatRange(n,o)}function bt(t,e){let r=/^(\d{1,2}):(\d{2})/.exec(t);if(!r)return t;let i=new Date(Date.UTC(1970,0,1,Number(r[1]),Number(r[2])));return ce(e,{hour:"numeric",minute:"2-digit"},!0).format(i)}function ie(t,e,r){return t&&e?`${bt(t,r)}\u2013${bt(e,r)}`:t?p(s.windowFrom,{time:bt(t,r)}):e?p(s.windowUntil,{time:bt(e,r)}):null}function U(t,e){if(!t)return"";let r=L(t);return r===null?t:ce(e,{dateStyle:"medium",timeStyle:"short"},!1).format(r)}var Ls={hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23"};function Os(t,e){return t%1e3!==0?!1:ce({language:"en-GB",hour12:void 0,timeZone:e},Ls,!1).formatToParts(t).every(i=>i.type==="literal"||i.value==="00")}function je(t,e){let r=t?L(t):null;if(r===null)return"";let i=ce(e,Xt,!1).format(r);return Os(r,e.timeZone)?i:p(s.dayAtTime,{day:i,time:ce(e,{timeStyle:"short"},!1).format(r)})}function de(t){if(typeof t!="string")return null;let e=t.trim();return e||null}function Ri(t){let e=t.trim();if(!/^[a-z0-9]+(?:[_-][a-z0-9]+)*$/.test(e))return e;let r=e.replace(/[_-]+/g," ");return r.charAt(0).toUpperCase()+r.slice(1)}function Ke(t,e){let r=de(e);return r?Object.hasOwn(t,r)?t[r]??r:Ri(r):""}function x(t){let e=de(t.carrier_name);if(e)return e;let r=de(t.carrier);return!r||r==="other"?null:Object.hasOwn(oe,r)?oi(r):Ri(r)}function M(t){return t.restricted?s.privateParcel:de(t.merchant)??de(t.name)??x(t)??de(t.tracking_number)??s.unnamedParcel}function Ti(t){let e=de(t.name);return e&&!t.restricted&&e!==M(t)?e:null}function Ci(t){return t.eta_source==="parcelapp"?ve(t.eta_source):null}function B(t){return Ke(ai,t)}function We(t){return Ke(pt,t)}function ve(t){return Ke(li,t)}function Ai(t){switch(t.inferred_reason){case"quiet":return s.inferredQuietNotice;case"return":return s.inferredReturnNotice;default:return s.inferredNotice}}function Ei(t){return Ke(ci,t)}function Pi(t){let e=de(t);return e&&Object.hasOwn(Vt,e)?Vt[e]??null:null}function vt(t){return Ke(di,t)}var yt="var(--secondary-text-color, #727272)",Ii="var(--info-color, #039be5)",Ms="var(--warning-color, #ffa600)",Ns="var(--success-color, #43a047)",Li="var(--error-color, #db4437)",Ds="var(--purple-color, #926bc7)",Oi={ordered:yt,shipped:Ii,in_transit:Ii,out_for_delivery:Ms,delivered:Ns,attempted:Li,exception:Li,ready_for_pickup:Ds,returned:yt,cancelled:yt};function qe(t){return Object.hasOwn(Oi,t)?Oi[t]:yt}var Fs=new Set(["delivered","returned","cancelled"]);function ye(t){return!Fs.has(t)}function P(t){let e=F(t.eta_start)?t.eta_start:null,r=F(t.eta_end)?t.eta_end:null,i=e??r;return i?{start:i,end:r&&$(r,i)>=0?r:i}:null}function ue(t){return ye(t.status)}function wt(t,e){let r=L(t.status_time),i=L(e.status_time);return r!==i?r===null?1:i===null?-1:i-r:t.id<e.id?-1:t.id>e.id?1:0}function Fi(t){return t.filter(e=>ue(e)&&!e.archived&&P(e)===null).sort(wt)}var Hs=7,Us=9999;function Mi(t){return t.replace(/[^0-9a-z]/gi,"").toUpperCase()}function Ni(t){return t.merchant?.trim().toLowerCase()??""}function Hi(t,e){return t.status!=="delivered"||t.inferred||t.delivered_undated?null:E(t.delivered_at,e)}function Di(t,e){let r=Hi(t,e);if(r)return{start:r,end:r};let i=P(t);if(i)return i;let n=E(t.delivered_at??t.status_time,e);return n?{start:n,end:n}:null}function Ui(t,e,r){let i=(n,o)=>{let a=Hi(n,r),c=E(o.shipped_at??o.ordered_at,r);return a!==null&&c!==null&&$(a,c)<0};return i(t,e)||i(e,t)}function er(t,e,r){let i=Di(t,r),n=Di(e,r);return!i||!n?Us:$(i.end,n.start)<0?le(i.end,n.start):$(n.end,i.start)<0?le(n.end,i.start):0}function tr(t,{timeZone:e}){let r=new Set(t.order_numbers.map(Mi).filter(Boolean)),i=Ni(t),n=o=>o.order_numbers.some(a=>r.has(Mi(a)))?0:i&&Ni(o)===i?1:2;return(o,a)=>n(o)-n(a)||+!ue(o)-+!ue(a)||er(t,o,e)-er(t,a,e)||wt(o,a)}function Bs(t,{today:e,timeZone:r}){if(t.archived||t.status==="cancelled")return!0;if(ue(t))return!1;let i=E(t.delivered_at??t.status_time,r);return i!==null&&le(i,e)>Hs}function Bi(t,e,r){let i=[],n=[];for(let o of t){if(o.id===e.id||o.restricted)continue;(Bs(o,r)||Ui(e,o,r.timeZone)?n:i).push(o)}return i.sort(tr(e,r)),n.sort(wt),{likely:i,older:n}}function zi(t,e){let r=e.toLowerCase().split(/\s+/).filter(Boolean);return r.length?t.filter(i=>{let n=[i.merchant,x(i),i.tracking_number,...i.order_numbers,...i.items].filter(Boolean).join(" ").toLowerCase();return r.every(o=>n.includes(o))}):[...t]}function ji(t){let e=new Map;for(let r of t??[]){let i=e.get(r.parcel.id)??[];for(let n of r.candidates)i.some(o=>o.id===n.id)||i.push(n);e.set(r.parcel.id,i)}return e}function rr(t,e){let r=[],i=new Set,n=(o,a,c)=>{i.has(a.id)||(i.add(a.id),r.push({suggestionId:o.id,parcel:a,candidateId:c,reason:o.reason}))};for(let o of t??[])if(o.parcel.id===e)for(let a of o.candidates)n(o,a,a.id);else o.candidates.some(a=>a.id===e)&&n(o,o.parcel,e);return r}function Ki(t,e,{timeZone:r}){let i=n=>er(t,n.parcel,r);return e.filter(n=>!Ui(t,n.parcel,r)).sort((n,o)=>i(n)-i(o)||wt(n.parcel,o.parcel))}function Wi(t,e,r){return rr(t,e).map(i=>i.parcel).filter(i=>i.id!==r&&!i.archived&&!i.restricted&&i.status!=="cancelled"&&i.status!=="returned"&&(i.items.length>0||i.order_numbers.length>0))}function qi(t){let e=t.length>1,r=t.some(i=>i.candidateId===i.parcel.id);return t.length&&t.every(i=>i.reason==="same_reference")?r?s.possibleHintShipment:e?s.possibleHintStemMany:s.possibleHintStemOne:r?e?s.possibleHintDeliveryMany:s.possibleHintDeliveryOne:e?s.possibleHintOrderMany:s.possibleHintOrderOne}function Vi(t,e,r){return e?.kind==="delivered"||e?.kind==="returned"?null:ie(t.window_start,t.window_end,r)}function Yi(t){return!t.restricted&&x(t)===null}function Qi(t){return t!==void 0&&t>1?p(s.packages,{count:String(t)}):null}function Ge(t){return t.restricted?s.privateParcel:$t(t.merchant)??s.unknownSeller}function sr(t){if(t.restricted)return null;let e=$t(t.pickup_code);return e?p(s.pin,{code:e}):null}function Zi(t,e){let r=e.placement??null,i=[],n=x(t);if(n&&i.push(n),e.showStatus){let c=B(t.status);c&&i.push(c)}let o=Qi(e.count);o&&i.push(o),e.showRange&&r&&r.from!==r.to&&i.push(O(r.from,r.to,e.locale));let a=Vi(t,r,e.locale);return a&&i.push(a),Yi(t)&&i.push(s.carrierNotKnown),i.join(" \xB7 ")}var zs=/^\d{1,3}\s*[x×]\s+/i,js=/\s*(?:[,;(|[]|\s[-–—]\s)/,Gi=8;function $t(t){if(typeof t!="string")return null;let e=t.replace(/\s+/g," ").trim();return e||null}function Ji(t){let e=t.replace(zs,""),r=e.search(js);return(r>0?e.slice(0,r):e).trim()||t}function Xi(t){let e=Ji(t).split(" ").slice(0,3);for(;e.length>1&&e.join(" ").length>24;)e.pop();return e.join(" ")}function Ks(t){let e=Ji(t).split(" "),r=e[0]??t;return r.length<4&&e.length>1?`${r} ${e[1]}`:r}function pe(t){if(t.restricted)return null;let e=(t.items??[]).map($t).filter(n=>n!==null);if(e.length===0)return null;if(e.length===1)return e[0]??null;let r=e.map(e.length===2?Xi:Ks),i=r.slice(0,Gi);return r.length>Gi&&i.push("\u2026"),`${p(s.itemsCount,{count:String(e.length)})} \xB7 ${i.join(", ")}`}function en(t){let e=(t.items??[]).map($t).filter(n=>n!==null),r=e[0];if(t.restricted||r===void 0)return null;let i=Xi(r);return e.length>1?p(s.itemsMore,{name:i,count:String(e.length-1)}):i}function tn(t){let e=t.length===1?t[0]:void 0;if(e!==void 0){let i=pe(e);return i?p(s.possibly,{items:i}):null}let r=[...new Set(t.map(en).filter(i=>i!==null))];return r.length?p(s.possibly,{items:r.join(s.possiblyOr)}):null}function rn(t,e){let{locale:r}=e,i=e.placement??null,n=[Ge(t)],o=Qi(e.count);o&&n.push(o);let a=x(t);a?n.push(p(s.carrierIs,{carrier:a})):Yi(t)&&n.push(s.carrierNotKnownLabel);let c=B(t.status),d=i?H(i.from,r):"";switch(i?.kind){case"delivered":n.push(p(s.deliveredOn,{date:d}));break;case"returned":n.push(p(s.returnedOn,{date:d}));break;case"pickup":n.push(p(s.readyForPickupSince,{date:d}));break;case"status":n.push(p(s.statusOn,{status:c,date:d}));break;case"eta":c&&n.push(c),n.push(p(s.expectedOn,{date:O(i.from,i.to,r)}));break;default:c&&n.push(c);break}let m=Vi(t,i,r);m&&n.push(m);let g=pe(t);if(g?n.push(g):e.possibly&&!t.restricted&&n.push(e.possibly),!t.restricted){t.ai?n.push(s.aiBadgeLabel):t.ai_filled&&n.push(s.aiFilledLabel),t.auto_merged&&n.push(s.autoMergedLabel),t.inferred&&n.push(s.inferredLabel);let h=sr(t);h?n.push(h):t.has_code&&n.push(s.hasCode)}return(t.private||t.restricted)&&n.push(s.privateLabel),e.continuesBefore&&n.push(s.continuesBefore),e.continuesAfter&&n.push(s.continuesAfter),n.join(", ")}function we(t){let e=t?.trim();if(!e)return null;if(e.length<=6)return e;let r=e.replace(/[^0-9a-z_]/gi,""),i="",n=0;for(let o=r.length-1;o>=0&&n<5;o-=1){let a=r.charAt(o);i=a+i,a!=="_"&&(n+=1)}return`\u2026${i.replace(/^_+/,"")}`}var ir=3;function Ws(t){let e=t.restricted?[]:t.senders??[];if(!e.length)return null;let r=e.slice(0,ir).map(i=>{let n=i.source!=="email",o=i.count<=1,a=n?o?s.candidateUpdate:s.candidateUpdates:o?s.candidateEmail:s.candidateEmails;return p(a,{count:String(i.count),name:i.name})});return e.length>ir&&r.push(p(s.candidateMore,{count:String(e.length-ir)})),r.join(", ")}function qs(t){let e=t.restricted?[]:t.senders??[],r=i=>i.source!=="email";return e.length&&e.every(r)?s.trackingNoItems:e.some(i=>i.carrier)&&e.every(i=>i.carrier||r(i))?s.carrierEmailsNoItems:s.itemsNotKnown}function Gs(t,e){let r=t.delivered_at??t.status_time;if(t.delivered_at?t.delivered_undated:t.status_undated)return s.dateNotKnownInline;if(!t.inferred){let a=je(r,e);if(a)return a}let n=e.timeZone??Intl.DateTimeFormat().resolvedOptions().timeZone,o=E(r,n);return o?O(o,o,e):null}function Ee(t,e){let r=[B(t.status)];if(ue(t)){let a=P(t);r.push(a?O(a.start,a.end,e):null,ie(t.window_start,t.window_end,e))}else r.push(Gs(t,e));let i=[x(t)??s.carrierNotKnown],n=we(t.tracking_number);n&&i.push(p(s.numberTail,{tail:n}));let o=we(t.order_numbers[0]);return o&&i.push(p(s.orderTail,{tail:o})),{title:Ge(t),when:r.filter(Boolean).join(" \xB7 "),carrier:i.join(" \xB7 "),items:pe(t),emails:Ws(t),noItems:qs(t)}}function Ve(t,e){let r=Ee(t,e);return[r.title,r.items,r.carrier,r.when].filter(Boolean).join(" \xB7 ")}var nr=3;function nn(t){let e=t.slice(0,nr).map(r=>{let i=en(r)??Ge(r),n=we(r.order_numbers[0]);return n?p(s.couldAlsoBeOrder,{items:i,tail:n}):i});return e.length?(t.length>nr&&e.push(p(s.candidateMore,{count:String(t.length-nr)})),p(s.couldAlsoBe,{list:e.join("; ")})):null}function or(t,e){let r=[],i=new Map;for(let n of t){let o=e(n),a=o===null?void 0:i.get(o);if(a){a.push(n);continue}let c=[n];r.push(c),o!==null&&i.set(o,c)}return r}function ar(t,...e){return t.restricted||t.shipment_group===null?null:JSON.stringify([t.shipment_group,t.status,...e])}function Pe(t,e){return t.id<e.id?-1:t.id>e.id?1:0}function sn(t){return or(t,e=>ar(e)).map(e=>{let r=[...e].sort(Pe);return{parcel:e.reduce((i,n)=>Pe(n,i)<0?n:i),members:r}})}function Vs(t){return t.reduce((e,r)=>r!==null&&(e===null||r<e)?r:e,null)}function Ys(t){return t.reduce((e,r)=>r!==null&&(e===null||r>e)?r:e,null)}function on(t,e){return e.length<2?t:{...t,window_start:Vs(e.map(r=>r.window_start)),window_end:Ys(e.map(r=>r.window_end)),ai:e.some(r=>r.ai),ai_filled:e.some(r=>r.ai_filled),private:e.some(r=>r.private),has_code:e.some(r=>r.has_code),pickup_code:Qs(e),items:Zs(t,e),auto_merged:e.find(r=>r.auto_merged)?.auto_merged??null,inferred:e.some(r=>r.inferred)}}function Qs(t){let e=new Set;for(let r of t){let i=r.pickup_code?.trim();i&&e.add(i)}return e.size>0?[...e].join(", "):null}function Zs(t,e){let r=[...t.items],i=new Set(r);for(let n of e)for(let o of n.items)i.has(o)||(i.add(o),r.push(o));return r}function an(t,e){let r=e.shipment_group;if(r===null||e.restricted)return[];let i=t.filter(n=>n.shipment_group===r&&!n.restricted).sort((n,o)=>(n.tracking_number??"").localeCompare(o.tracking_number??"","en",{numeric:!0})||Pe(n,o));return i.length>1?i:[]}var ln="var(--pink-color, #e91e63)",Ie="mdi:package-up",Js={email:s.pickupRuleEmail,next_working_day:s.pickupRuleNextWorkingDay,assumed:s.pickupRuleAssumed};function cn(t){let e=t?.replace(/\s+/g," ").trim();return e||null}function $e(t,e){return t.received||$(t.day,e)<0}function ke(t){return t.restricted?s.privateReturn:cn(t.merchant)??s.unknownSeller}function lr(t){return t?Js[t]:null}function dn(t){return t.restricted?null:x(t)}function Ye(t,e){return t.received?s.returnReceived:t.pickup===null?s.returnStarted:$e(t,e)?s.returnPickedUp:s.returnPickup}function un(t,e){let r=Ye(t,e),i=dn(t);return i?`${r} \xB7 ${i}`:r}function pn(t,e,r){let i=t.restricted?null:cn(t.merchant),n=[t.restricted?s.privateReturn:i?p(s.returnTo,{merchant:i}):s.returnPlain],o=H(t.day,e);if(t.pickup===null)n.push(p(s.returnStartedOn,{date:o}));else if($e(t,r))$(t.day,r)<=0&&n.push(p(s.pickedUpOn,{date:o}));else{n.push(p(s.pickupOn,{date:o}));let d=lr(t.pickup_rule);d&&n.push(d)}t.received&&n.push(s.receivedByShopLabel);let a=dn(t);a&&n.push(p(s.carrierIs,{carrier:a}));let c=pe(t);return c&&n.push(c),(t.private||t.restricted)&&n.push(s.privateLabel),n.join(", ")}function hn(t,e){return t.filter(r=>r.parcel_ids.includes(e))}function dr(t){return`.chip[data-parcels~="${CSS.escape(t)}"] button.chip-main`}function mn(t,e,r,i){let n=e?"true":"false";return l`<div class="merge-note">
    <ha-icon icon=${t.icon} aria-hidden="true"></ha-icon>
    <span class="merge-label"
      >${t.label}${t.detail?l` <span class="merge-detail">${t.detail}</span>`:u}</span
    >
    <button
      type="button"
      class="link-btn"
      aria-label=${t.undoLabel}
      aria-disabled=${n}
      @click=${r}
    >
      ${s.undo}
    </button>
    <button
      type="button"
      class="link-btn"
      aria-label=${t.keepLabel}
      aria-disabled=${n}
      @click=${i}
    >
      ${s.keep}
    </button>
  </div>`}function Xs(t,e,r){let i=r&&(t.tracking_number?.trim()??null)||null;return{title:i?`${e} ${i}`:e,detail:i}}function eo(t,e,r){let{title:i,detail:n}=e;return mn({icon:"mdi:call-merge",label:s.autoMerged,detail:n,undoLabel:p(s.undoMergeLabel,{title:i}),keepLabel:p(s.keepMergeLabel,{title:i})},r.busy,()=>r.onUndoMerge(t),()=>r.onKeepMerge(t))}function to(t,e,r){let{title:i,detail:n}=e;return mn({icon:"mdi:package-variant-closed-check",label:s.inferred,detail:n,undoLabel:p(s.undoInferredLabel,{title:i}),keepLabel:p(s.keepInferredLabel,{title:i})},r.busy,()=>r.onUndoInferred(t),()=>r.onKeepInferred(t))}var cr="\xA0";function kt(t,e){let{locale:r}=e,i=e.placement??null,n=e.members&&e.members.length>1?e.members:[t],o=n.length>1,a=on(t,n),c=M(a),d=sr(a),m=pe(a),g=m===null&&!a.restricted?e.possibly??null:null,h=rn(a,{locale:r,placement:i,count:n.length,continuesBefore:e.continuesBefore,continuesAfter:e.continuesAfter,possibly:g}),_=Zi(a,{locale:r,placement:i,count:n.length,showStatus:e.showStatus,showRange:e.showRange}),f={chip:!0,"cont-before":e.continuesBefore===!0,"cont-after":e.continuesAfter===!0,returned:a.status==="returned"},v={...e.position,"--chip-color":qe(a.status)},A=l`<span class="chip-row" aria-hidden=${a.restricted?"true":u}>
    ${e.continuesBefore?l`<span class="cont">‹</span>`:u}
    ${a.status==="delivered"?l`<span class="check">✓</span>`:u}
    <span class="chip-text">
      <span class=${be({"chip-title":!0,unknown:!a.restricted&&!a.merchant?.trim()})}
        >${Ge(a)}</span
      >
      <span class="chip-line">
        <span class="chip-meta">${_||cr}</span>
        ${d?l`<span class="chip-pin">${d}</span>`:u}
      </span>
      <span
        class=${be({"chip-items":!0,unknown:m===null&&g===null&&!a.restricted,possibly:g!==null})}
        >${m??g??(a.restricted?cr:s.itemsNotKnown)}</span
      >
    </span>
    ${(a.ai||a.ai_filled)&&!a.restricted?l`<span class="badge ai">${s.aiBadge}</span>`:u}
    ${a.has_code&&!d&&!a.restricted?l`<ha-icon class="lock" icon="mdi:dialpad" title=${s.hasCode}></ha-icon>`:u}
    ${a.private||a.restricted?l`<ha-icon class="lock" icon="mdi:lock"></ha-icon>`:u}
    ${e.continuesAfter?l`<span class="cont">›</span>`:u}
  </span>`;return a.restricted?l`<div class=${be(f)} style=${z(v)}>
      <div class="chip-main" title=${h}>
        <span class="sr-only">${h}</span>
        ${A}
      </div>
    </div>`:l`<div
    class=${be(f)}
    style=${z(v)}
    data-parcel-id=${a.id}
    data-parcels=${n.map(T=>T.id).join(" ")}
  >
    <button
      type="button"
      class="chip-main"
      aria-haspopup="dialog"
      aria-label=${h}
      title=${h}
      @click=${T=>e.onOpen(t,T.currentTarget)}
    >
      ${A}
    </button>
    ${n.map(T=>{let S=Xs(T,c,o);return l`${T.auto_merged?eo(T,S,e):u}${T.inferred?to(T,S,e):u}`})}
  </div>`}function ur(t){return`.chip[data-return-id="${CSS.escape(t)}"] button.chip-main`}function fn(t,e){let r=pn(t,e.locale,e.today),i=pe(t),n={chip:!0,return:!0,done:$e(t,e.today)},o={...e.position,"--chip-color":ln},a=l`<span class="chip-row" aria-hidden=${t.restricted?"true":u}>
    <ha-icon class="ret-icon" icon=${Ie}></ha-icon>
    <span class="chip-text">
      <span class="chip-title">${ke(t)}</span>
      <span class="chip-line">
        <span class="chip-meta">${un(t,e.today)}</span>
      </span>
      <span class="chip-items">${i??cr}</span>
    </span>
    ${t.private||t.restricted?l`<ha-icon class="lock" icon="mdi:lock"></ha-icon>`:u}
  </span>`;return t.restricted?l`<div class=${be(n)} style=${z(o)}>
      <div class="chip-main" title=${r}>
        <span class="sr-only">${r}</span>
        ${a}
      </div>
    </div>`:l`<div class=${be(n)} style=${z(o)} data-return-id=${t.id}>
    <button
      type="button"
      class="chip-main"
      aria-haspopup="dialog"
      aria-label=${r}
      title=${r}
      @click=${c=>e.onOpen(t,c.currentTarget)}
    >
      ${a}
    </button>
  </div>`}function gn(t,e){return e&&!t.restricted&&!t.archived&&ue(t)&&P(t)===null}function xt(t){return typeof t=="number"&&Number.isInteger(t)&&t>0?t:0}function pr(t){let e=t!==null&&typeof t=="object"?t:{};return{read:xt(e.read),queued:xt(e.queued),gone:xt(e.gone),failed:xt(e.failed)}}function St(t,e,r){return t<=0?null:t===1?e:p(r,{count:t})}function _n(t,e){if(t.read+t.gone+t.failed===0)return s.checkAgainNoEmails;let r=[St(t.read,s.checkAgainReadOne,s.checkAgainReadMany),St(t.gone,s.checkAgainGoneOne,s.checkAgainGoneMany),St(t.failed,s.checkAgainFailedOne,s.checkAgainFailedMany)];return t.queued>0?r.push(St(t.queued,s.checkAgainQueuedOne,s.checkAgainQueuedMany),e.mode==="suggest"?s.checkAgainSuggest:s.checkAgainAuto):t.read>0&&r.push(e.enabled?s.checkAgainNothingForAi:s.checkAgainAiOff),r.filter(i=>i!==null).join(" ")}function C(t){return typeof t=="object"&&t!==null&&!Array.isArray(t)}function b(t){return typeof t=="string"?t:null}function w(t){return typeof t=="string"?t:""}function I(t){return Array.isArray(t)?t.filter(e=>typeof e=="string"):[]}function y(t){return typeof t=="string"&&t!==""?t:null}function Qe(t){return Number.isSafeInteger(t)&&t>0?t:0}function ro(t){return typeof t=="number"&&Number.isFinite(t)&&t>=0?t:null}function V(t,e){if(!Array.isArray(t))return[];let r=[];for(let i of t){let n=e(i);n!==null&&r.push(n)}return r}function io(t){return t==="shop"||t==="return"||t==="quiet"?t:null}function Ze(t){return t==="ai"||t==="manual"||t==="seventeentrack"||t==="parcelapp"?t:"parser"}function no(t){return typeof t=="string"&&t?Ze(t):null}function so(t){return!C(t)||!y(t.origin)?null:{origin:w(t.origin),at:w(t.at),reason:w(t.reason)}}function oo(t){if(!C(t))return null;let e=y(t.name);return e?{name:e,source:t.source==="seventeentrack"||t.source==="parcelapp"?t.source:"email",carrier:t.carrier===!0,count:Math.max(1,Qe(t.count))}:null}function Rt(t){if(!C(t))return null;let e=y(t.id);return e?{id:e,merchant:b(t.merchant),seller:b(t.seller),name:b(t.name),carrier:b(t.carrier),carrier_name:b(t.carrier_name),tracking_number:b(t.tracking_number),tracking_url:b(t.tracking_url),status:w(t.status),status_time:b(t.status_time),status_undated:t.status_undated===!0,eta_start:b(t.eta_start),eta_end:b(t.eta_end),window_start:b(t.window_start),window_end:b(t.window_end),eta_source:no(t.eta_source),delivered_at:b(t.delivered_at),delivered_undated:t.delivered_undated===!0,inferred:t.inferred===!0,inferred_reason:io(t.inferred_reason),pickup_point:b(t.pickup_point),pickup_code:b(t.pickup_code),has_code:t.has_code===!0,order_numbers:I(t.order_numbers),references:I(t.references),items:I(t.items),private:t.private===!0,owners:I(t.owners),source:Ze(t.source),ai:t.ai===!0,ai_filled:t.ai_filled===!0,auto_merged:so(t.auto_merged),provisional:t.provisional===!0,archived:t.archived===!0,origins:I(t.origins),shipment_group:y(t.shipment_group),restricted:t.restricted===!0,senders:V(t.senders,oo),ordered_at:y(t.ordered_at),shipped_at:y(t.shipped_at)}:null}function ao(t){return C(t)?{kind:w(t.kind),merchant:b(t.merchant),carrier:b(t.carrier),tracking_numbers:I(t.tracking_numbers),order_numbers:I(t.order_numbers),eta_start:b(t.eta_start),eta_end:b(t.eta_end),window_start:b(t.window_start),window_end:b(t.window_end),pickup_point:b(t.pickup_point),pickup_code:b(t.pickup_code),items:I(t.items),reference:b(t.reference)}:null}function lo(t){if(!C(t))return null;let e=y(t.id);return e?{id:e,created:w(t.created),received:b(t.received),sender:w(t.sender),sender_domain:w(t.sender_domain),subject:w(t.subject),mailbox_owner:b(t.mailbox_owner),reason:w(t.reason),authenticated:t.authenticated===!0,trusted_sender:t.trusted_sender===!0,checks:uo(t.checks),fill:t.fill===!0,errors:bn(t.errors),notes:bn(t.notes),source:t.source==="ai"?"ai":"parser",suggestion:ao(t.suggestion)}:null}var co=/^[a-z0-9_]{1,40}$/;function bn(t){if(!Array.isArray(t))return[];let e=t.filter(r=>typeof r=="string"&&co.test(r));return[...new Set(e)]}function uo(t){if(!C(t))return null;let e=Qe(t.headers),r=t.used;return{headers:e,servers:Array.isArray(t.servers)?t.servers.map(i=>typeof i=="string"?i:""):[],used:Number.isSafeInteger(r)&&r>=0&&r<e?r:null,dkim:w(t.dkim),dmarc:w(t.dmarc),spf:w(t.spf),originals:Qe(t.originals)}}function po(t){if(!C(t))return null;let e=y(t.id);return e?{id:e,created:w(t.created),received:b(t.received),sender:w(t.sender),sender_domain:w(t.sender_domain),subject:w(t.subject),removed:t.removed===!0}:null}function ho(t){if(!C(t))return null;let e=y(t.id),r=Rt(t.parcel),i=V(t.candidates,Rt);return!e||!r||!i.length?null:{id:e,reason:w(t.reason),merchant:b(t.merchant),day:F(t.day)?t.day:null,parcel:r,candidates:i}}function mo(t){return t==="suggest"||t==="auto"?t:"off"}function fo(t,e=Date.now()){let r=C(t)?t:{},i=y(r.time_zone)??"UTC",n=F(r.today)?r.today:E(new Date(e).toISOString(),i)??"1970-01-01";return{user_is_admin:r.user_is_admin===!0,ai_enabled:r.ai_enabled===!0,ai_mode:mo(r.ai_mode),ai_queue:Qe(r.ai_queue),ai_queue_seconds:ro(r.ai_queue_seconds),dashboard_url:w(r.dashboard_url),seventeentrack:r.seventeentrack===!0,time_zone:i,today:n}}function vn(t,e=Date.now()){let r=C(t)?t:{};return{parcels:V(r.parcels,Rt),returns:V(r.returns,bo),review:V(r.review,lo),merge_suggestions:V(r.merge_suggestions,ho),filtered:V(r.filtered,po),settings:fo(r.settings,e)}}function go(t){return t==="email"||t==="next_working_day"||t==="assumed"?t:null}function _o(t){return C(t)?{time:b(t.time),label:w(t.label),source:Ze(t.source)}:null}function bo(t){if(!C(t))return null;let e=y(t.id);return!e||!F(t.day)?null:{id:e,merchant:b(t.merchant),carrier:b(t.carrier),carrier_name:b(t.carrier_name),tracking_number:b(t.tracking_number),tracking_url:b(t.tracking_url),day:t.day,pickup:F(t.pickup)?t.pickup:null,pickup_rule:go(t.pickup_rule),started:b(t.started),received:t.received===!0,order_numbers:I(t.order_numbers),items:I(t.items),parcel_ids:I(t.parcel_ids),emails:V(t.emails,_o),private:t.private===!0,owners:I(t.owners),archived:t.archived===!0,restricted:t.restricted===!0}}function vo(t){return t==="inferred"||t==="inferred_return"||t==="quiet"?t:Ze(t)}function yo(t){return C(t)?{time:w(t.time),status:w(t.status),source:vo(t.source),label:w(t.label),undated:t.undated===!0}:null}function wo(t){return C(t)?{id:w(t.id),merchant:b(t.merchant),number:w(t.number),placed_at:b(t.placed_at),parcel_ids:I(t.parcel_ids)}:null}function $o(t){if(!Array.isArray(t)||t.length!==2)return null;let[e,r]=t.map(Qe);return e&&r&&e<=r?[e,r]:null}function ko(t){if(!C(t))return null;let e=y(t.id);return e?{id:e,label:w(t.label),source:Ze(t.source),sender_name:y(t.sender_name),name:y(t.name),time:b(t.time),status:y(t.status),kind:y(t.kind),event_time:y(t.event_time),undated:t.undated===!0,dayless:t.dayless===!0,eta_start:F(t.eta_start)?t.eta_start:null,eta_end:F(t.eta_end)?t.eta_end:null,window_start:y(t.window_start),window_end:y(t.window_end),carrier:y(t.carrier),carrier_name:y(t.carrier_name),tracking_number:y(t.tracking_number),reference:y(t.reference),merchant:y(t.merchant),seller:y(t.seller),order_numbers:I(t.order_numbers),items:I(t.items),pickup_point:y(t.pickup_point),shipment:$o(t.shipment),email:t.email===!0,edits:t.edits===!0,part_of:y(t.part_of),split_blocked:y(t.split_blocked)}:null}function yn(t){if(!C(t))return null;let e=Rt(t.parcel);return e?{parcel:e,timeline:V(t.timeline,yo),orders:V(t.orders,wo),origins:V(t.origins,ko)}:null}var xo=6e4;function xe(t){let e=t?.trim();return e||null}function So(t,e){let r=[t,...e],i=r.find(d=>d.status||d.kind)??t,n=r.find(d=>d.eta_start||d.window_start||d.window_end)??t,o=r.find(d=>d.carrier||d.carrier_name)??t,a=d=>r.find(m=>m[d]!==null&&m[d]!=="")?.[d]??t[d],c=d=>[...new Set(r.flatMap(m=>m[d]))];return{...t,status:i.status,kind:i.kind,event_time:i.event_time,undated:i.undated,dayless:i.dayless,eta_start:n.eta_start,eta_end:n.eta_end,window_start:n.window_start,window_end:n.window_end,carrier:o.carrier,carrier_name:o.carrier_name,tracking_number:a("tracking_number"),reference:a("reference"),merchant:a("merchant"),seller:a("seller"),pickup_point:a("pickup_point"),shipment:a("shipment"),name:a("name"),order_numbers:c("order_numbers"),items:c("items")}}function Ro(t){return t.edits?s.originEdits:t.email?xe(t.sender_name)??xe(t.label)??s.originEmail:xe(t.label)??ve(t.source)}function To(t,e){let r=[],n=(t.kind&&t.kind!=="unknown"&&t.kind!=="not_parcel"?We(t.kind):"")||(t.status?B(t.status):"");if(n){r.push(n);let a=t.event_time?L(t.event_time):null,c=t.time?L(t.time):null;t.undated?r.push(s.dateNotKnownInline):a!==null&&(c===null||Math.abs(a-c)>=xo)&&r.push(je(t.event_time,e))}if(t.eta_start){let a=O(t.eta_start,t.eta_end??t.eta_start,e);r.push(p(s.expectedOn,{date:a}))}let o=ie(t.window_start,t.window_end,e);return o&&r.push(o),r.join(" \xB7 ")}function Co(t){let e=[],r=xe(t.merchant);r&&e.push(p(s.factShop,{name:r}));let i=xe(t.seller);i&&e.push(p(s.factSeller,{name:i}));for(let m of t.order_numbers){let g=we(m);g&&e.push(p(s.orderTail,{tail:g}))}if(t.shipment){let[m,g]=t.shipment;e.push(p(s.factShipment,{n:String(m),total:String(g)}))}let n=x(t),o=we(t.tracking_number);n&&o?e.push(p(s.factCarrierNumber,{carrier:n,tail:o})):n?e.push(n):o&&e.push(p(s.numberTail,{tail:o}));let a=we(t.reference);a&&e.push(p(s.factReference,{tail:a}));let c=xe(t.pickup_point);c&&e.push(p(s.factPickup,{place:c}));let d=xe(t.name);return d&&e.push(p(s.factName,{name:d})),e}function wn(t,e){let r=new Set(t.map(o=>o.id)),i=new Map;for(let o of t)o.part_of&&o.part_of!==o.id&&r.has(o.part_of)&&i.set(o.part_of,[...i.get(o.part_of)??[],o]);let n=[];for(let o of t){if(o.part_of&&o.part_of!==o.id&&r.has(o.part_of))continue;let a=i.get(o.id)??[],c=So(o,a),d=Ro(c),m=null;o.source==="ai"?m="all":a.length&&(m="part"),n.push({ids:[o.id,...a.map(g=>g.id)],lead:o.id,header:d,when:je(o.time,e),said:To(c,e),facts:Co(c),items:c.items.filter(g=>g.trim()),ai:m,email:o.email,edits:o.edits,splitBlocked:o.split_blocked,sender:`${o.email?"email":o.source}:${d}`})}return n}function $n(t){let e=new Map,r=new Map;for(let o of t){if(!o.email||o.edits)continue;let a=e.get(o.sender),c=[...o.facts,...o.items.map(d=>`\0${d}`)];a&&c.every(d=>a.has(d))&&r.set(o.sender,[...r.get(o.sender)??[],o]),e.set(o.sender,new Set([...a??[],...c]))}let i=new Map;for(let o of r.values())if(o.length>=2)for(let a of o)i.set(a.lead,o);let n=[];for(let o of t){let a=i.get(o.lead);if(!a){n.push({type:"row",row:o});continue}let c=a[a.length-1];c.lead===o.lead&&n.push({type:"repeats",key:c.lead,header:o.header,rows:a,latest:c})}return n}function kn(t){let e=t.every(r=>r.email)?s.originsTitle:s.originsAndUpdatesTitle;return p(e,{count:String(t.length)})}function xn(t,e){let r=new Set(e);return t.filter(i=>r.has(i.lead)).flatMap(i=>i.ids)}function Sn(t){switch(t){case null:return null;case"nothing_left":return s.splitBlockedNothingLeft;case"shared_number":return s.splitBlockedShared;default:return s.splitBlockedOther}}function Rn(t,e,r){let i=t.parcels[0];return t.review!==null?{notice:"review",follow:null,show:null}:t.parcels.includes(e)?{notice:"restored",follow:null,show:null}:i===void 0?{notice:"noParcel",follow:null,show:null}:r?{notice:"restored",follow:i,show:null}:{notice:"elsewhere",follow:null,show:i}}function Tt(t){if(typeof t!="string")return null;let e=t.trim();if(!e)return null;let r;try{r=new URL(e)}catch{return null}return r.protocol!=="https:"||!r.hostname||r.username||r.password?null:r.href}var Tn={parcel:/^p_[0-9a-f]{1,64}$/,return:/^ret_[0-9a-f]{1,64}$/};function Cn(t){return Object.hasOwn(Tn,t)}function An(t){try{return decodeURIComponent(t.replaceAll("+"," "))}catch{return t}}function En(t){return t.replace(/^\?/,"").split("&").filter(e=>e!=="")}function Pn(t){let e=t.indexOf("=");return An(e<0?t:t.slice(0,e))}function In(t){for(let e of En(t)){let r=Pn(e);if(!Cn(r))continue;let i=e.indexOf("="),n=i<0?"":An(e.slice(i+1));if(Tn[r].test(n))return{kind:r,id:n}}return null}function Ln(t){let e=En(t),r=e.filter(i=>!Cn(Pn(i)));return r.length===e.length?t:r.length?`?${r.join("&")}`:""}var Ao={restored:s.restoredNotice,elsewhere:s.restoredElsewhereNotice,review:s.restoredReviewNotice,noParcel:s.restoredNoParcelNotice},Eo={weekday:"short",day:"numeric",month:"short",year:"numeric"},On={eta_start:"",eta_end:"",window_start:"",window_end:""},Po=6;function Io(t){return t.map((e,r)=>({entry:e,index:r,time:L(e.time)??-1/0})).sort((e,r)=>r.time-e.time||r.index-e.index).map(({entry:e})=>e)}var hr=class extends ae{static properties={snapshot:{attribute:!1},locale:{attribute:!1},_parcelId:{state:!0},_details:{state:!0},_loading:{state:!0},_loadError:{state:!0},_mode:{state:!0},_copyState:{state:!0},_dateForm:{state:!0},_formError:{state:!0},_mergeTarget:{state:!0},_mergeQuery:{state:!0},_mergeOlder:{state:!0},_mergeHint:{state:!0},_splitSelection:{state:!0},_pendingPrivate:{state:!0},_checking:{state:!0},_checkStatus:{state:!0},_originsOpen:{state:!0},_openFolds:{state:!0},_originNotice:{state:!0}};static styles=[W,Ce,R`
      .merge-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        min-width: 0;
        margin: 8px 0 0;
        padding: 0;
        border: 0;
      }
      .merge-option {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 8px 10px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
        cursor: pointer;
      }
      .merge-option:has(input:checked) {
        border-color: var(--primary-color, #03a9f4);
        box-shadow: inset 0 0 0 1px var(--primary-color, #03a9f4);
      }
      .merge-option input {
        flex: none;
        width: 18px;
        height: 18px;
        margin: 1px 0 0;
        accent-color: var(--primary-color, #03a9f4);
      }
      .merge-lines {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
        font-size: 0.875rem;
      }
      .merge-line {
        overflow-wrap: anywhere;
      }
      .merge-line.items {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .merge-hint {
        color: var(--error-color, #db4437);
      }
      .possible-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin: 8px 0 0;
        padding: 0;
        list-style: none;
      }
      .possible-item {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        padding: 8px 10px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
      }
      .possible-item .merge-lines {
        flex: 1 1 12rem;
      }
      .possible-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .facts {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin: 8px 0 0;
      }
      .facts > div {
        display: grid;
        grid-template-columns: minmax(6rem, 32%) minmax(0, 1fr);
        gap: 12px;
        align-items: baseline;
      }
      .facts dt {
        color: var(--secondary-text-color, #727272);
        font-size: 0.875rem;
      }
      .facts dd {
        margin: 0;
        overflow-wrap: anywhere;
      }
      .facts ul {
        margin: 0;
        padding-inline-start: 18px;
      }
      .link {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-inline-start: 8px;
        --mdc-icon-size: 16px;
      }
      .copy-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
      }
      .copy-row input {
        flex: 1 1 12rem;
        width: auto;
        min-width: 0;
        font-family: var(--code-font-family, monospace);
      }
      .copy-status:empty {
        display: none;
      }
      .copy-status {
        flex-basis: 100%;
      }
      .switch-row {
        margin-top: 12px;
      }
      .origins > summary {
        cursor: pointer;
      }
      .origins > .hint {
        margin-bottom: 8px;
      }
      .origin-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .origin-list .origin-list {
        margin-top: 6px;
      }
      .origin {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
        padding: 8px 10px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
        font-size: 0.875rem;
      }
      .origin .row-actions {
        margin-top: 6px;
      }
      .origin-line {
        overflow-wrap: anywhere;
      }
      .origin-items {
        margin: 2px 0 0;
        padding-inline-start: 18px;
        overflow-wrap: anywhere;
      }
      span.origin-items {
        display: flex;
        flex-direction: column;
        padding-inline-start: 0;
      }
      .fold-toggle {
        display: inline-flex;
        align-items: center;
        gap: 2px;
        padding-inline-start: 0;
        text-align: start;
        --mdc-icon-size: 18px;
      }
      .split-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .split-row {
        align-items: flex-start;
        padding: 8px 10px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
      }
      .split-row input {
        flex: none;
        width: 18px;
        height: 18px;
        margin: 1px 0 0;
      }
      .origin-body {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
        font-size: 0.875rem;
      }
      .timeline {
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .timeline li {
        position: relative;
        padding: 0 0 12px 22px;
      }
      .timeline li::before {
        content: "";
        position: absolute;
        inset-inline-start: 5px;
        top: 14px;
        bottom: 0;
        border-inline-start: 2px solid var(--divider-color, rgba(0, 0, 0, 0.12));
      }
      .timeline li:last-child::before {
        display: none;
      }
      .timeline .dot {
        position: absolute;
        inset-inline-start: 0;
        top: 4px;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: var(--dot-color);
      }
      .timeline .entry-title {
        font-weight: 500;
      }
      .timeline .entry-meta {
        font-size: 0.8125rem;
        color: var(--secondary-text-color, #727272);
      }
      fieldset {
        margin: 0;
        padding: 0;
        border: none;
      }
      legend {
        margin-bottom: 8px;
        padding: 0;
      }
    `];_request=0;_checkRun=0;_loadedKey="";_rowsCache=null;constructor(){super(),this.snapshot=null,this.locale=Ae(void 0),this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._copyState="idle",this._dateForm=On,this._formError=null,this._mergeTarget="",this._mergeQuery="",this._mergeOlder=!1,this._mergeHint=!1,this._splitSelection=[],this._pendingPrivate=null,this._checking=!1,this._checkStatus=null,this._originsOpen=!1,this._openFolds=new Set,this._originNotice=null}async open(e,r=null){this._parcelId=e,this._details=null,this._loadError=null,this._mode="view",this._copyState="idle",this._formError=null,this._pendingPrivate=null,this._checkRun+=1,this._checking=!1,this._checkStatus=null,this._resetOrigins(),this._load(),await this.showDialog(r)}_switchTo(e){this._busy||e===this._parcelId||(this._parcelId=e,this._details=null,this._loadError=null,this._error=null,this._mode="view",this._copyState="idle",this._formError=null,this._pendingPrivate=null,this._checkStatus=null,this._resetOrigins(),this._load(),this.focusAfterRender("[data-current-package]"))}_resetOrigins(){this._originsOpen=!1,this._openFolds=new Set,this._originNotice=null}dialogClosed(){this._request+=1,this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._pendingPrivate=null,this._checkRun+=1,this._checking=!1,this._checkStatus=null,this._resetOrigins()}canLightDismiss(){return this._mode==="view"&&!this._busy}willUpdate(e){if(super.willUpdate(e),!e.has("snapshot")||!this.isOpen||!this.snapshot)return;this._pendingPrivate=null;let r=this.snapshot.parcels.find(i=>i.id===this._parcelId);r&&JSON.stringify(r)!==this._loadedKey&&this._load()}get _parcel(){let e=this._parcelId;return e===null?null:this.snapshot?this.snapshot.parcels.find(r=>r.id===e)??null:this._details?.parcel??null}async _load(){let e=this.hass,r=this._parcelId;if(!e||r===null)return;let i=++this._request,n=this.snapshot?.parcels.find(o=>o.id===r);this._loadedKey=n?JSON.stringify(n):"",this._loading=!0,this._loadError=null;try{let o=await j(e,"get",{parcel_id:r});if(i!==this._request)return;let a=yn(o);if(!a)throw new Error(s.unknownError);this._details=a}catch(o){i===this._request&&(this._loadError=q(o))}finally{i===this._request&&(this._loading=!1)}}renderContent(){let e=this._parcel;return l`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">
            ${e?M(e):s.details}
          </h2>
          ${e?this._renderBadges(e):u}
        </div>
        <button
          type="button"
          class="icon-btn"
          data-autofocus
          aria-label=${s.close}
          title=${s.close}
          @click=${this.closeDialog}
        >
          <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
        </button>
      </div>
      <div class="dialog-content">${this._renderBody(e)}</div>
      ${this._error?l`<div class="dialog-error">
            <div class="alert error" role="alert">
              <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
              <span class="grow">${this._error}</span>
            </div>
          </div>`:u}
      ${this._mode==="view"?this._renderStatus():u}
      ${e&&!e.restricted?this._renderActions(e):u}
    `}_renderStatus(){let e=this._originNotice,r=this._busy?"true":"false";return l`<div class="dialog-status" role="status">
      ${e?l`<div class="alert" data-origin-notice>
            <ha-icon icon="mdi:email-check-outline" aria-hidden="true"></ha-icon>
            <span class="grow">${e.text}</span>
            ${e.show?l`<button
                  type="button"
                  class="btn"
                  aria-label=${s.showOtherParcelLabel}
                  aria-disabled=${r}
                  @click=${()=>this._showParcel(e.show)}
                >
                  ${s.showOtherParcel}
                </button>`:u}
            ${e.undo?l`<button type="button" class="btn" aria-disabled=${r} @click=${e.undo}>
                  ${s.undo}
                </button>`:u}
            <button
              type="button"
              class="icon-btn"
              aria-label=${s.dismissMessage}
              title=${s.dismissMessage}
              @click=${this._dismissOriginNotice}
            >
              <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
            </button>
          </div>`:u}
      ${this._checkStatus?l`<div class="alert">
            <ha-icon icon="mdi:email-sync-outline" aria-hidden="true"></ha-icon>
            <span class="grow">${this._checkStatus}</span>
            <button
              type="button"
              class="icon-btn"
              aria-label=${s.dismissMessage}
              title=${s.dismissMessage}
              @click=${this._dismissCheckStatus}
            >
              <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
            </button>
          </div>`:u}
    </div>`}_renderBadges(e){let r=e.ai?s.aiBadgeLabel:s.aiFilledLabel;return l`<div class="dialog-badges">
      <span class="badge" style=${z({"--badge-color":qe(e.status)})}>
        ${B(e.status)}
      </span>
      ${(e.ai||e.ai_filled)&&!e.restricted?l`<span class="badge ai" title=${r}>
            ${s.aiBadge}<span class="sr-only">, ${r}</span>
          </span>`:u}
      ${e.private||e.restricted?l`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${s.private}
          </span>`:u}
      ${e.provisional?l`<span class="badge info">${s.provisional}</span>`:u}
      ${this._returnsOf(e).length?l`<span class="badge return">
            <ha-icon icon=${Ie} aria-hidden="true"></ha-icon>${s.returnBadge}
          </span>`:u}
      ${e.archived?l`<span class="badge">${s.archived}</span>`:u}
    </div>`}_returnsOf(e){return e.restricted?[]:hn(this.snapshot?.returns??[],e.id)}_renderBody(e){if(!e)return this.snapshot||!this._loading&&!this._loadError?l`<p class="empty">${s.notFound}</p>`:this._renderLoadState();switch(this._mode){case"date":return this._renderDateForm();case"merge":return this._renderMerge(e);case"split":return this._renderSplit();case"archive":return l`<p>${s.archiveQuestion}</p>`;default:return this._renderView(e)}}_renderLoadState(){return this._loadError?l`<div class="alert error" role="alert">
        <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
        <span class="grow">${p(s.detailsError,{message:this._loadError})}</span>
        <button type="button" class="btn" @click=${this._load}>${s.retry}</button>
      </div>`:l`<p class="empty" role="status">${s.loadingDetails}</p>`}_renderView(e){let r=e.restricted;return l`
      ${!r&&(e.ai||e.ai_filled)?l`<div class="alert">
            <ha-icon icon="mdi:robot-outline" aria-hidden="true"></ha-icon>
            <span class="grow">${e.ai?s.aiNotice:s.aiFilledNotice}</span>
            <button
              type="button"
              class="btn"
              aria-label=${e.ai?s.confirmLabel:s.confirmFilledLabel}
              aria-disabled=${this._busy?"true":"false"}
              @click=${this._confirm}
            >
              ${s.confirm}
            </button>
          </div>`:u}
      ${!r&&e.auto_merged?this._renderMergeNotice(e):u}
      ${!r&&e.inferred?this._renderInferredNotice(e):u}
      ${!r&&e.provisional?l`<p class="hint">${s.provisionalHint}</p>`:u}
      ${r?u:this._renderPossible(e)}
      ${this._renderFacts(e)}
      ${r?u:l`<label class="check-row switch-row">
            <input
              type="checkbox"
              role="switch"
              .checked=${D(this._pendingPrivate??e.private)}
              aria-disabled=${this._busy?"true":"false"}
              @click=${this._onPrivateClick}
              @change=${this._togglePrivate}
            />
            <span>${s.fieldPrivate}</span>
          </label>`}
      ${r?u:this._renderOrigins()}
      <h3 class="section-title">${s.timeline}</h3>
      ${this._details?this._renderTimeline(this._details.timeline):this._renderLoadState()}
    `}get _rows(){let e=this._details;if(!e)return[];let r=this._rowsCache;if(r?.details===e&&r.locale===this.locale)return r.rows;let i=wn(e.origins,this.locale);return this._rowsCache={details:e,locale:this.locale,rows:i},i}get _splitRows(){return this._rows.filter(e=>!e.edits)}get _splitChosen(){let e=new Set(this._splitRows.map(r=>r.lead));return this._splitSelection.filter(r=>e.has(r))}_renderOrigins(){let e=this._rows;if(!e.length)return u;let r=this._splitRows.length>=2;return l`<details class="origins" .open=${this._originsOpen} @toggle=${this._onOriginsToggle}>
      <summary class="section-title" data-origins-summary>${kn(e)}</summary>
      <p class="hint">${s.originsHint}</p>
      <ol class="origin-list">
        ${$n(e).map(i=>this._renderOriginEntry(i,r))}
      </ol>
    </details>`}_renderOriginEntry(e,r){if(e.type==="row")return l`<li class="origin" data-origin=${e.row.lead}>
        ${this._renderOriginBody(e.row,!1)}${this._renderRowActions(e.row,r)}
      </li>`;let i=this._openFolds.has(e.key),n=e.latest.said;return l`<li class="origin fold">
      <span class="origin-line">
        <button
          type="button"
          class="link-btn fold-toggle"
          aria-expanded=${i?"true":"false"}
          @click=${()=>this._toggleFold(e.key)}
        >
          <ha-icon icon=${i?"mdi:chevron-up":"mdi:chevron-down"} aria-hidden="true"></ha-icon>
          ${p(s.originRepeats,{count:String(e.rows.length),sender:e.header})}
        </button>
        ${n?l`<span class="muted">· ${p(s.originRepeatsLatest,{said:n})}</span>`:u}
      </span>
      ${i?l`<ol class="origin-list">
            ${e.rows.map(o=>l`<li class="origin" data-origin=${o.lead}>
                ${this._renderOriginBody(o,!1)}${this._renderRowActions(o,r)}
              </li>`)}
          </ol>`:u}
    </li>`}_renderOriginBody(e,r){let i=u;e.items.length&&r?i=l`<span class="origin-line origin-items">
        ${e.items.map(o=>l`<span class="origin-item">${o}</span>`)}
      </span>`:e.items.length&&(i=l`<ul class="origin-items" aria-label=${s.originItems}>
        ${e.items.map(o=>l`<li>${o}</li>`)}
      </ul>`);let n=e.ai==="all"?s.originAiAll:s.originAiPart;return l`<span class="origin-line">
        <strong>${e.header}</strong>${e.when?l`<span class="muted"> · ${e.when}</span>`:u}${e.ai?l`<span class="muted"> · ${n}</span>`:u}
      </span>
      ${e.said?l`<span class="origin-line">${e.said}</span>`:u}
      ${e.facts.length?l`<span class="origin-line muted">${e.facts.join(" \xB7 ")}</span>`:u}
      ${i}`}_renderRowActions(e,r){let i=e.email&&this.snapshot?.settings.user_is_admin===!0;if(e.edits||!r&&!i)return u;let n=r?Sn(e.splitBlocked):null,o=this._busy?"true":"false",a=e.when?`${e.header} \xB7 ${e.when}`:e.header,c=u;return n?c=l`<span class="hint">${n}</span>`:r&&(c=l`<button
        type="button"
        class="btn"
        data-move
        aria-label=${p(s.moveToNewParcelLabel,{row:a})}
        aria-disabled=${o}
        @click=${()=>this._moveRow(e)}
      >
        ${s.moveToNewParcel}
      </button>`),l`<span class="row-actions">
      ${c}
      ${i?l`<button
            type="button"
            class="btn"
            data-remove
            aria-label=${p(s.removeFromParcelsLabel,{row:a})}
            aria-disabled=${o}
            @click=${()=>this._removeRow(e)}
          >
            ${s.removeFromParcels}
          </button>`:u}
    </span>`}_renderPossible(e){let r=this.snapshot?.merge_suggestions,i=Ki(e,rr(r,e.id),this._dayContext());if(!i.length)return u;let n=this.locale,o=this._busy?"true":"false",a=M(e);return l`<section class="possible" aria-labelledby="possible-title">
      <h3 class="section-title" id="possible-title">${s.possibleMatches}</h3>
      <p class="hint">${qi(i)}</p>
      <ul class="possible-list">
        ${i.map(c=>{let d=Ve(c.parcel,n);return l`<li class="possible-item" data-possible=${c.parcel.id}>
            ${this._renderCandidateLines(c.parcel,e.id)}
            <span class="possible-actions">
              <button
                type="button"
                class="btn"
                data-accept
                aria-label=${p(s.mergeSuggestedLabel,{candidate:d,title:a})}
                aria-disabled=${o}
                @click=${()=>this._acceptPossible(c)}
              >
                ${s.mergeSuggested}
              </button>
              <button
                type="button"
                class="btn"
                data-dismiss
                aria-label=${p(s.notThisOneLabel,{candidate:d,title:a})}
                aria-disabled=${o}
                @click=${()=>this._dismissPossible(c)}
              >
                ${s.notThisOne}
              </button>
            </span>
          </li>`})}
      </ul>
    </section>`}_renderMergeNotice(e){let r=vt(e.auto_merged?.reason),i=this._busy?"true":"false",n=M(e);return l`<div class="alert warning">
      <ha-icon icon="mdi:call-merge" aria-hidden="true"></ha-icon>
      <span class="grow">
        ${r?p(s.mergedNotice,{reason:r}):s.mergedNoticeNoReason}
      </span>
      <button
        type="button"
        class="btn"
        aria-label=${p(s.undoMergeLabel,{title:n})}
        aria-disabled=${i}
        @click=${this._undoMerge}
      >
        ${s.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${p(s.keepMergeLabel,{title:n})}
        aria-disabled=${i}
        @click=${this._keepMerge}
      >
        ${s.keep}
      </button>
    </div>`}_renderInferredNotice(e){let r=this._busy?"true":"false",i=M(e);return l`<div class="alert warning">
      <ha-icon icon="mdi:package-variant-closed-check" aria-hidden="true"></ha-icon>
      <span class="grow">${Ai(e)}</span>
      <button
        type="button"
        class="btn"
        aria-label=${p(s.undoInferredLabel,{title:i})}
        aria-disabled=${r}
        @click=${this._undoInferred}
      >
        ${s.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${p(s.keepInferredLabel,{title:i})}
        aria-disabled=${r}
        @click=${this._keepInferred}
      >
        ${s.keep}
      </button>
    </div>`}_renderFacts(e){let r=this.locale,i=P(e),n=ie(e.window_start,e.window_end,r),o=x(e),a=e.restricted?null:Tt(e.tracking_url),c=e.tracking_number?.trim()??"",d=this._details?.orders??[],m=an(this.snapshot?.parcels??[],e),g=this._details?.parcel.id===e.id?this._details.parcel:null,h=e.has_code?g?.pickup_code??null:null,_=this._returnsOf(e),f=(S,Xn)=>l`<div><dt>${S}</dt><dd>${Xn}</dd></div>`,v=e.status_undated?` \xB7 ${s.dateNotKnownInline}`:e.status_time?` \xB7 ${p(s.sinceDate,{date:U(e.status_time,r)})}`:"",A=Ci(e),T=Ti(e);return l`<dl class="facts">
      ${f(s.status,`${B(e.status)}${v}`)}
      ${e.delivered_undated?f(s.delivered,s.dateNotKnown):e.delivered_at?f(s.delivered,U(e.delivered_at,r)):u}
      ${i?f(s.expected,`${O(i.start,i.end,r,Eo)}${A?` \xB7 ${A}`:""}`):u}
      ${n?f(s.timeWindow,n):u}
      ${_.length?f(s.returnBadge,l`<ul>
              ${_.map(S=>this._renderReturnLink(S))}
            </ul>`):u}
      ${o||a||!e.restricted?f(s.carrier,l`${o??(e.restricted?"":s.notKnownYet)}${a?l`<a class="link" href=${a} target="_blank" rel="noopener noreferrer">
                  ${s.trackOnline}<span class="sr-only"> ${s.opensInNewTab}</span>
                  <ha-icon icon="mdi:open-in-new" aria-hidden="true"></ha-icon>
                </a>`:u}`):u}
      ${c?l`<div>
            <dt><label for="tracking-number">${s.trackingNumber}</label></dt>
            <dd class="copy-row">
              <input id="tracking-number" readonly .value=${c} spellcheck="false" />
              <button
                type="button"
                class="btn"
                aria-label=${s.copyTrackingNumber}
                @click=${this._copy}
              >
                <ha-icon icon="mdi:content-copy" aria-hidden="true"></ha-icon>${s.copy}
              </button>
              <span class="copy-status hint" role="status">
                ${this._copyState==="copied"?s.copied:this._copyState==="failed"?s.copyFailed:""}
              </span>
            </dd>
          </div>`:u}
      ${m.length?f(s.packagesInShipment,l`<ul class="packages">
              ${m.map(S=>this._renderPackage(S,e.id))}
            </ul>`):u}
      ${e.merchant?f(s.merchant,e.merchant):u}
      ${e.seller?f(s.seller,e.seller):u}
      ${T?f(s.parcelAppName,T):u}
      ${d.length?f(s.orders,l`<ul>
              ${d.map(S=>l`<li>
                    ${S.number}${S.placed_at?` \xB7 ${U(S.placed_at,r)}`:""}
                  </li>`)}
            </ul>`):e.order_numbers.length?f(s.orders,e.order_numbers.join(", ")):u}
      ${e.references.length?f(s.references,e.references.join(", ")):u}
      ${e.items.length?f(s.items,l`<ul>
              ${e.items.map(S=>l`<li>${S}</li>`)}
            </ul>`):u}
      ${e.pickup_point?f(s.pickupPoint,e.pickup_point):u}
      ${h?f(s.pickupCode,h):u}
      ${e.restricted?u:f(s.parcelId,e.id)}
    </dl>`}_renderReturnLink(e){let r=this.snapshot?.settings.today??"",i=`${Ye(e,r)} \xB7 ${H(e.day,this.locale)}`;return e.restricted?l`<li>${i}</li>`:l`<li>
      <button
        type="button"
        class="link-btn"
        aria-haspopup="dialog"
        aria-disabled=${this._busy?"true":"false"}
        @click=${()=>this._openReturn(e.id)}
      >
        ${i}
      </button>
    </li>`}_openReturn(e){this._busy||(this.closeDialog(),this.dispatchEvent(new CustomEvent(hi,{detail:e})))}_renderPackage(e,r){let i=this.locale,n=e.tracking_number?.trim()||M(e),o=P(e),a=e.delivered_undated?s.dateNotKnownInline:e.delivered_at?U(e.delivered_at,i):o?O(o.start,o.end,i):"",c=[B(e.status),a].filter(Boolean).join(" \xB7 ");return e.id===r?l`<li aria-current="true" tabindex="-1" data-current-package>
        <strong>${n}</strong>${c?` \xB7 ${c}`:""}
      </li>`:l`<li>
      <button
        type="button"
        class="link-btn"
        aria-label=${p(s.showPackage,{name:n})}
        aria-disabled=${this._busy?"true":"false"}
        @click=${()=>this._switchTo(e.id)}
      >
        ${n}</button
      >${c?` \xB7 ${c}`:""}
    </li>`}_renderTimeline(e){if(!e.length)return l`<p class="muted">${s.noTimeline}</p>`;let r=this.locale;return l`<ol class="timeline">
      ${Io(e).map(i=>{let n=B(i.status),o=i.label.trim(),c=[i.undated?s.dateNotKnown:U(i.time,r),ve(i.source)].filter(Boolean).join(" \xB7 ");return l`<li style=${z({"--dot-color":qe(i.status)})}>
          <span class="dot" aria-hidden="true"></span>
          <div class="entry-title">${n}</div>
          ${o&&o!==n?l`<div>${o}</div>`:u}
          ${c?l`<div class="entry-meta">${c}</div>`:u}
        </li>`})}
    </ol>`}_renderDateForm(){let e=this._dateForm,r=this._formError,i=(n,o,a,c=!1)=>{let d=r?.field===n;return l`<label class="field">
        <span class="field-label">${o}</span>
        <input
          type=${a}
          name=${n}
          .value=${D(e[n])}
          ?data-first=${c}
          aria-invalid=${d?"true":"false"}
          aria-describedby=${d?"date-error":u}
          @input=${this._onDateInput}
        />
      </label>`};return l`<form id="date-form" novalidate @submit=${this._saveDate}>
      <div class="form-grid">
        ${i("eta_start",s.fieldEtaStart,"date",!0)}
        ${i("eta_end",s.fieldEtaEnd,"date")}
        ${i("window_start",s.fieldWindowStart,"time")}
        ${i("window_end",s.fieldWindowEnd,"time")}
      </div>
      ${r?l`<div class="alert error" id="date-error" role="alert">
            <span class="grow">${r.message}</span>
          </div>`:u}
    </form>`}_renderMerge(e){let{pool:r,shown:i,target:n}=this._mergeChoice(e),o=r.likely.length+r.older.length;if(!o)return l`<p class="empty">${s.noMergeCandidates}</p>`;let a=this._mergeQuery.trim()!=="",c=o>Po,d=this._mergeOlder&&!a?r.likely.length:-1,m=!a&&!this._mergeOlder&&r.older.length>0;return l`<p id="merge-intro">${s.mergeIntro}</p>
      ${c?l`<label class="field">
            <span class="field-label">${s.mergeSearch}</span>
            <input
              type="search"
              data-first
              autocomplete="off"
              placeholder=${s.mergeSearchPlaceholder}
              .value=${D(this._mergeQuery)}
              @input=${this._onMergeQuery}
            />
          </label>`:u}
      <fieldset class="merge-list" aria-describedby="merge-intro">
        <legend class="sr-only">${s.mergeChoose}</legend>
        ${i.map((g,h)=>this._renderCandidate(g,e.id,{checked:g.id===n,first:!c&&h===0,olderFirst:h===d}))}
        ${a&&!i.length?l`<p class="empty">${s.mergeNoMatch}</p>`:u}
      </fieldset>
      ${m?l`<button
            type="button"
            class="link-btn"
            ?data-first=${!c&&!i.length}
            @click=${this._showOlderMerge}
          >
            ${p(s.mergeShowOlder,{count:String(r.older.length)})}
          </button>`:u}
      ${this._mergeHint&&!n?l`<p class="hint merge-hint" role="alert">${s.mergeChooseFirst}</p>`:u}`}_renderCandidate(e,r,i){return l`<label class="merge-option">
      <input
        type="radio"
        name="merge-target"
        value=${e.id}
        .checked=${D(i.checked)}
        ?data-first=${i.first}
        ?data-older-first=${i.olderFirst}
        @change=${this._onMergeTarget}
      />
      ${this._renderCandidateLines(e,r)}
    </label>`}_renderCandidateLines(e,r){let i=Ee(e,this.locale),n=i.items?null:nn(Wi(this.snapshot?.merge_suggestions,e.id,r));return l`<span class="merge-lines">
      <span class="merge-line"><strong>${i.title}</strong> · ${i.when}</span>
      <span class="merge-line muted">${i.carrier}</span>
      ${i.emails?l`<span class="merge-line muted">${i.emails}</span>`:u}
      <span class="merge-line items ${i.items?"":"muted"}">
        ${i.items??i.noItems}
      </span>
      ${n?l`<span class="merge-line items" data-also>${n}</span>`:u}
    </span>`}_dayContext(){let e=this.snapshot?.settings;return{today:e?.today??"",timeZone:e?.time_zone??Intl.DateTimeFormat().resolvedOptions().timeZone}}_renderSplit(){return l`<fieldset aria-describedby="split-hint">
        <legend>${s.splitIntro}</legend>
        <div class="split-list">
          ${this._splitRows.map((e,r)=>l`<label class="check-row split-row">
              <input
                type="checkbox"
                .value=${e.lead}
                .checked=${D(this._splitSelection.includes(e.lead))}
                ?data-first=${r===0}
                @change=${this._onSplitChange}
              />
              <span class="origin-body">${this._renderOriginBody(e,!0)}</span>
            </label>`)}
        </div>
      </fieldset>
      <p class="hint" id="split-hint">${s.splitHint}</p>`}_renderActions(e){let r=this._busy?"true":"false",i=l`<button type="button" class="btn" data-cancel @click=${this._backToView}>
      ${s.cancel}
    </button>`;switch(this._mode){case"date":return l`<div class="dialog-actions">
          ${i}
          <button type="submit" form="date-form" class="btn primary" aria-disabled=${r}>
            ${s.save}
          </button>
        </div>`;case"merge":{let{pool:n,target:o}=this._mergeChoice(e);return l`<div class="dialog-actions">
          ${i}
          ${n.likely.length+n.older.length?l`<button
                type="button"
                class="btn primary"
                aria-disabled=${this._busy||!o?"true":"false"}
                @click=${this._merge}
              >
                ${s.mergeConfirm}
              </button>`:u}
        </div>`}case"split":{let n=Qt(this._splitChosen,this._splitRows.length);return l`<div class="dialog-actions">
          ${i}
          <button
            type="button"
            class="btn primary"
            aria-disabled=${this._busy||!n?"true":"false"}
            @click=${this._split}
          >
            ${s.splitConfirm}
          </button>
        </div>`}case"archive":return l`<div class="dialog-actions">
          ${i}
          <button
            type="button"
            class="btn primary danger"
            aria-disabled=${r}
            @click=${this._archive}
          >
            ${s.archive}
          </button>
        </div>`;default:{let n=this._splitRows.length>=2;return l`<div class="dialog-actions" role="group" aria-label=${s.actions}>
          <button type="button" class="btn" data-mode="date" @click=${this._editDate}>
            ${s.editDate}
          </button>
          ${gn(e,this.snapshot?.settings.user_is_admin===!0)?l`<button
                type="button"
                class="btn"
                data-check-again
                title=${s.checkAgainHint}
                aria-disabled=${r}
                @click=${this._checkAgain}
              >
                ${this._checking?s.checkingAgain:s.checkAgain}
              </button>`:u}
          <button type="button" class="btn" data-mode="merge" @click=${this._startMerge}>
            ${s.mergeWith}
          </button>
          ${n?l`<button type="button" class="btn" data-mode="split" @click=${this._startSplit}>
                ${s.split}
              </button>`:u}
          ${e.archived?u:l`<button
                type="button"
                class="btn danger"
                data-mode="archive"
                @click=${this._startArchive}
              >
                ${s.archive}
              </button>`}
          ${ye(e.status)?l`<span class="spacer"></span>
                <button
                  type="button"
                  class="btn primary"
                  aria-disabled=${r}
                  @click=${this._markDelivered}
                >
                  <ha-icon icon="mdi:check" aria-hidden="true"></ha-icon>${s.markDelivered}
                </button>`:u}
        </div>`}}}_setMode(e){this._mode=e,this._error=null,this._formError=null,this.focusAfterRender(e==="archive"?"[data-cancel]":"[data-first], [data-cancel]")}_backToView(){let e=this._mode;this._mode="view",this._error=null,this._formError=null,this.focusAfterRender(`[data-mode="${e}"]`)}_editDate(){let e=this._parcel;this._dateForm=e?bi(e):On,this._setMode("date")}_startMerge(){this._mergeTarget="",this._mergeQuery="",this._mergeOlder=!1,this._mergeHint=!1,this._setMode("merge")}_startSplit(){this._splitSelection=[],this._setMode("split")}_startArchive(){this._setMode("archive")}_parcelService(e,r,i){let n=this.hass,o=this._parcel;!n||!o||this.runAction(()=>te(n,e,{parcel_id:o.id,...r}),i)}_confirm(){this._parcelService("update",{confirm:!0})}_undoMerge(){this._parcelService("undo_merge",{})}_keepMerge(){this._parcelService("update",{confirm_merge:!0})}_undoInferred(){this._parcelService("undo_delivery",{})}_keepInferred(){this._parcelService("update",{confirm_delivery:!0})}_markDelivered(){this._parcelService("mark_delivered",{})}async _checkAgain(){let e=this.hass,r=this._parcel;if(!e||!r||this._busy)return;let i=++this._checkRun,n=pr(null);this._checkStatus=null,this._checking=!0,await this.runAction(async()=>{let o=await j(e,"parcel/check_again",{parcel_id:r.id});n=pr(o)},()=>{let o=this.snapshot?.settings;this._checkStatus=_n(n,{enabled:o?.ai_enabled===!0,mode:o?.ai_mode??"off"})}),i===this._checkRun&&(this._checking=!1)}_dismissCheckStatus(){this._checkStatus=null}_archive(){this._parcelService("archive",{},()=>this.closeDialog())}_onPrivateClick(e){this._busy&&e.preventDefault()}_togglePrivate(e){let r=e.currentTarget.checked,i=this.hass,n=this._parcel;!i||!n||this._busy||(this._pendingPrivate=r,this.runAction(async()=>{try{await te(i,"update",{parcel_id:n.id,private:r})}catch(o){throw this._pendingPrivate=null,o}}))}_onDateInput(e){let r=e.currentTarget,i=r.name;this._dateForm={...this._dateForm,[i]:r.value},this._formError=null}_saveDate(e){e.preventDefault();let r=this._parcel;if(!r||this._busy)return;let i=this._dateForm,n=gt(i);if(n){this._formError=n,this.focusAfterRender(`[name="${n.field}"]`);return}let o=vi(r.id,i);this._parcelService("update",o,()=>this._backToView())}_mergePool(e){let r=this.snapshot;return r?Bi(r.parcels,e,this._dayContext()):{likely:[],older:[]}}_mergeChoice(e){let r=this._mergePool(e),i=this._mergeQuery.trim(),n=r.likely;i?n=zi([...r.likely,...r.older],i):this._mergeOlder&&(n=[...r.likely,...r.older]);let o=n.some(a=>a.id===this._mergeTarget)?this._mergeTarget:"";return{pool:r,shown:n,target:o}}_onMergeTarget(e){this._mergeTarget=e.currentTarget.value,this._mergeHint=!1}_onMergeQuery(e){this._mergeQuery=e.currentTarget.value}_showOlderMerge(){this._mergeOlder=!0,this.focusAfterRender("[data-older-first]")}_acceptPossible(e){let r=this.hass;if(!r)return;let i=null;this.runAction(async()=>{let n=await j(r,"suggestion/accept",{suggestion_id:e.suggestionId,parcel_id:e.candidateId});i=typeof n?.parcel_id=="string"?n.parcel_id:null},()=>{i!==null&&i!==this._parcelId&&(this._parcelId=i,this._details=null,this._loadError=null,this._load()),this.focusAfterRender("[data-autofocus]")})}_dismissPossible(e){let r=this.hass;r&&this.runAction(()=>j(r,"suggestion/dismiss",{suggestion_id:e.suggestionId,parcel_id:e.candidateId}),()=>{this.focusAfterRender("[data-autofocus]")})}_merge(){let e=this.hass,r=this._parcel;if(!e||!r)return;let{target:i}=this._mergeChoice(r);if(!i){this._mergeHint=!0,this.focusAfterRender('input[name="merge-target"]');return}this.runAction(()=>te(e,"merge",{parcel_ids:[r.id,i]}),()=>this._backToView())}_onSplitChange(e){let r=e.currentTarget,i=this._splitSelection.filter(n=>n!==r.value);this._splitSelection=r.checked?[...i,r.value]:i}_split(){let e=this._splitRows,r=this._splitChosen;Qt(r,e.length)&&this._parcelService("split",{origins:xn(e,r)},()=>this._backToView())}_onOriginsToggle(e){this._originsOpen=e.currentTarget.open}_toggleFold(e){let r=new Set(this._openFolds);r.delete(e)||r.add(e),this._openFolds=r}_dismissOriginNotice(){this._originNotice=null}_showParcel(e){e!==null&&this._switchTo(e)}async _focusOrigins(){if(await this.updateComplete,!this.isOpen)return;let e=this.renderRoot.querySelector("dialog [data-origins-summary]");e?e.focus():this.focusInDialog("[data-autofocus]")}_moveRow(e){let r=this.hass,i=this._parcel;if(!r||!i||this._busy)return;let n=i.id,o=null;this._originNotice=null,this.runAction(async()=>{o=await si(r,"split",{parcel_id:n,origins:e.ids})},()=>{let a=o;this._originNotice={text:s.movedNotice,undo:a===null?null:()=>this._moveBack(n,a),show:a},this._load(),this._focusOrigins()})}_moveBack(e,r){let i=this.hass;!i||this._busy||this.runAction(()=>te(i,"merge",{parcel_ids:[e,r]}),()=>{this._originNotice={text:s.movedBackNotice,undo:null,show:null},this._load(),this._focusOrigins()})}_removeRow(e){let r=this.hass,i=this._parcel;if(!r||!i||this._busy)return;let n=i.id,o=null,a=!0;this._originNotice=null,this.runAction(async()=>{let c=await j(r,"origin/remove",{parcel_id:n,origin_id:e.lead});o=typeof c?.filtered_id=="string"?c.filtered_id:null,a=typeof c?.parcel_id=="string"},()=>{let c=o;this._originNotice={text:a?s.removedNotice:s.removedGoneNotice,undo:c===null?null:()=>this._restoreRow(c,n),show:null},a&&this._load(),this._focusOrigins()})}_restoreRow(e,r){let i=this.hass;if(!i||this._busy)return;let n=null,o=[];this.runAction(async()=>{let a=await j(i,"review/restore",{filtered_id:e});n=typeof a?.review_id=="string"?a.review_id:null;let c=a?.parcel_ids;o=Array.isArray(c)?c.filter(d=>typeof d=="string"):[]},()=>{let a=this._parcelId===r&&!this.snapshot?.parcels.some(d=>d.id===r),c=Rn({review:n,parcels:o},r,a);c.follow!==null&&(this._parcelId=c.follow,this._details=null,this._loadError=null),this._originNotice={text:Ao[c.notice],undo:null,show:c.show},this._load(),this._focusOrigins()})}async _copy(e){let r=e.currentTarget,i=this._parcel?.tracking_number?.trim();if(!i)return;this._copyState="idle";try{if(!navigator.clipboard?.writeText)throw new Error("Clipboard API unavailable");await navigator.clipboard.writeText(i),this._copyState="copied";return}catch{}let n=this.renderRoot.querySelector("#tracking-number");n?.focus(),n?.select();let o=!1;try{o=document.execCommand("copy")}catch{o=!1}this._copyState=o?"copied":"failed",o&&r.focus()}};K("parcels-details-dialog",hr);var mr=["all","active","recent","completed"],Ct={all:s.filterAll,active:s.filterActive,recent:s.filterRecent,completed:s.filterCompleted},At="parcels-filter",Et="parcels-filter-changed";function fr(t){return typeof t=="string"&&mr.includes(t)}function Mn(){try{return globalThis.localStorage??null}catch{return null}}function Pt(t=Mn()){try{let e=t?.getItem(At);return fr(e)?e:"all"}catch{return"all"}}function Nn(t,e=Mn(),r=globalThis.window??null){try{e?.setItem(At,t)}catch{}r?.dispatchEvent(new CustomEvent(Et,{detail:t}))}function Lo(t,{today:e,timeZone:r}){let i=ze(e),n=re(i,6),o=c=>c!==null&&$(c,i)>=0&&$(c,n)<=0;if(o(E(t.status_time,r))||o(E(t.delivered_at,r)))return!0;let a=P(t);return a!==null&&$(a.start,n)<=0&&$(a.end,i)>=0}function Dn(t,e,r){switch(e){case"active":return ye(t.status);case"completed":return!ye(t.status);case"recent":return Lo(t,r);default:return!0}}function Fn(t,e,{today:r}){switch(e){case"active":return!$e(t,r);case"completed":return $e(t,r);case"recent":{let i=ze(r);return $(t.day,i)>=0&&$(t.day,re(i,6))<=0}default:return!0}}var gr=class extends ae{static properties={snapshot:{attribute:!1},locale:{attribute:!1},_returnId:{state:!0},_mode:{state:!0}};static styles=[W,Ce,R`
      .facts {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin: 12px 0 0;
      }
      .facts > div {
        display: grid;
        grid-template-columns: minmax(6rem, 32%) minmax(0, 1fr);
        gap: 12px;
        align-items: baseline;
      }
      .facts dt {
        color: var(--secondary-text-color, #727272);
        font-size: 0.875rem;
      }
      .facts dd {
        margin: 0;
        overflow-wrap: anywhere;
      }
      .facts ul {
        margin: 0;
        padding-inline-start: 18px;
      }
      .facts .hint {
        margin-top: 2px;
      }
      .link {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-inline-start: 8px;
        --mdc-icon-size: 16px;
      }
      .emails .entry-meta {
        font-size: 0.8125rem;
        color: var(--secondary-text-color, #727272);
      }
    `];constructor(){super(),this.snapshot=null,this.locale=Ae(void 0),this._returnId=null,this._mode="view"}async open(e,r=null){this._returnId=e,this._mode="view",await this.showDialog(r)}dialogClosed(){this._returnId=null,this._mode="view"}canLightDismiss(){return this._mode==="view"&&!this._busy}get _return(){let e=this._returnId;return e===null?null:this.snapshot?.returns.find(r=>r.id===e)??null}renderContent(){let e=this._return,r=this.snapshot?.settings.today??"";return l`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">
            ${e?ke(e):s.returnDetails}
          </h2>
          ${e?this._renderBadges(e,r):u}
        </div>
        <button
          type="button"
          class="icon-btn"
          data-autofocus
          aria-label=${s.close}
          title=${s.close}
          @click=${this.closeDialog}
        >
          <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
        </button>
      </div>
      <div class="dialog-content">${this._renderBody(e)}</div>
      ${this._error?l`<div class="dialog-error">
            <div class="alert error" role="alert">
              <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
              <span class="grow">${this._error}</span>
            </div>
          </div>`:u}
      ${e&&!e.restricted&&this.snapshot?.settings.user_is_admin===!0?this._renderActions():u}
    `}_renderBadges(e,r){return l`<div class="dialog-badges">
      <span class="badge return">
        <ha-icon icon=${Ie} aria-hidden="true"></ha-icon>${Ye(e,r)}
      </span>
      ${e.private||e.restricted?l`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${s.private}
          </span>`:u}
      ${e.archived?l`<span class="badge">${s.archived}</span>`:u}
    </div>`}_renderBody(e){return e?this._mode==="remove"?l`<p>${s.removeReturnQuestion}</p>`:l`<p class="hint">${s.returnHint}</p>
      ${this._renderFacts(e)}`:l`<p class="empty">${s.returnNotFound}</p>`}_renderFacts(e){let r=this.locale,i=(m,g)=>l`<div><dt>${m}</dt><dd>${g}</dd></div>`,n=lr(e.pickup_rule),o=e.restricted?null:x(e),a=e.restricted?null:Tt(e.tracking_url),c=e.tracking_number?.trim()??"",d=this._parcels(e);return l`<dl class="facts">
      ${e.pickup?i(s.pickup,l`${H(e.pickup,r)}${n?l`<div class="hint">${n}</div>`:u}`):u}
      ${e.started?i(s.returnStartedDay,U(e.started,r)):u}
      ${o||a?i(s.returnCarrier,l`${o??""}${a?l`<a class="link" href=${a} target="_blank" rel="noopener noreferrer">
                  ${s.trackOnline}<span class="sr-only"> ${s.opensInNewTab}</span>
                  <ha-icon icon="mdi:open-in-new" aria-hidden="true"></ha-icon>
                </a>`:u}`):u}
      ${c?i(s.trackingNumber,c):u}
      ${e.order_numbers.length?i(s.orders,e.order_numbers.join(", ")):u}
      ${e.items.length?i(s.items,l`<ul>
              ${e.items.map(m=>l`<li>${m}</li>`)}
            </ul>`):u}
      ${d.length?i(s.returnSentBackFrom,l`<ul>
              ${d.map(m=>this._renderParcel(m))}
            </ul>`):u}
      ${e.emails.length?i(s.returnEmails,this._renderEmails(e)):u}
    </dl>`}_parcels(e){let r=this.snapshot?.parcels??[];return e.parcel_ids.flatMap(i=>r.find(n=>n.id===i)??[])}_renderParcel(e){let r=M(e),i=e.delivered_undated?s.dateNotKnownInline:e.delivered_at?U(e.delivered_at,this.locale):"",n=[B(e.status),i].filter(Boolean).join(" \xB7 ");return e.restricted?l`<li>${r} · ${n}</li>`:l`<li>
      <button
        type="button"
        class="link-btn"
        aria-haspopup="dialog"
        aria-label=${p(s.showParcel,{name:r})}
        aria-disabled=${this._busy?"true":"false"}
        @click=${()=>this._openParcel(e.id)}
      >
        ${r}</button
      > · ${n}
    </li>`}_renderEmails(e){let r=this.locale;return l`<ul class="emails">
      ${e.emails.map(i=>{let n=i.label.trim(),o=[i.time?U(i.time,r):"",ve(i.source)].filter(Boolean).join(" \xB7 ");return l`<li>
          ${n?l`<div>${n}</div>`:u}
          <div class="entry-meta">${o}</div>
        </li>`})}
    </ul>`}_renderActions(){let e=this._busy?"true":"false";return this._mode==="remove"?l`<div class="dialog-actions">
        <button type="button" class="btn" data-cancel @click=${this._backToView}>
          ${s.cancel}
        </button>
        <button
          type="button"
          class="btn primary danger"
          aria-disabled=${e}
          @click=${this._remove}
        >
          ${s.removeReturn}
        </button>
      </div>`:l`<div class="dialog-actions" role="group" aria-label=${s.actions}>
      <span class="spacer"></span>
      <button type="button" class="btn danger" data-mode="remove" @click=${this._startRemove}>
        ${s.removeReturn}
      </button>
    </div>`}_startRemove(){this._mode="remove",this._error=null,this.focusAfterRender("[data-cancel]")}_backToView(){this._mode="view",this._error=null,this.focusAfterRender('[data-mode="remove"]')}_remove(){let e=this.hass,r=this._return;!e||!r||this.runAction(()=>j(e,"return/remove",{return_id:r.id}),()=>this.closeDialog())}_openParcel(e){this._busy||(this.closeDialog(),this.dispatchEvent(new CustomEvent(pi,{detail:e})))}};K("parcels-return-dialog",gr);var Oo="parcels/subscribe",Hn=[2e3,1e4,3e4,6e4,3e5],It=new Map,Mo=0;function Bn(t,e){try{t(e)}catch(r){console.error(r)}}function Un(t,e){t.state=e;for(let r of[...t.listeners.values()])Bn(r,e)}function zn(t){try{t().catch(()=>{})}catch{}}function Ot(t){t.retryTimer!==void 0&&(clearTimeout(t.retryTimer),t.retryTimer=void 0)}function Lt(t){t.connection.removeEventListener("ready",t.onReady),t.connection.removeEventListener("disconnected",t.onDisconnected)}function No(t){Ot(t);let e=Hn[Math.min(t.retries,Hn.length-1)]??3e5;t.retries+=1,t.retryTimer=setTimeout(()=>{t.retryTimer=void 0,_r(t)},e)}function _r(t){if(t.released||t.unsubscribe||t.pending||t.listeners.size===0)return;Ot(t);let e=++t.attempt,r=t.epoch,i=()=>!t.released&&t.attempt===e;t.pending=!0;let n;try{n=t.connection.subscribeMessage(o=>{i()&&(t.retries=0,Un(t,{snapshot:vn(o),error:null}))},{type:Oo},{resubscribe:!1})}catch(o){n=Promise.reject(o)}n.then(o=>{if(i()){t.pending=!1,t.unsubscribe=o;return}t.epoch===r&&zn(o),t.released&&t.attempt===e+1&&(t.pending=!1,Lt(t))},o=>{i()?(t.pending=!1,Un(t,{snapshot:t.state.snapshot,error:q(o)}),No(t)):t.released&&t.attempt===e+1&&(t.pending=!1,Lt(t))})}function Do(t,e){if(!t.listeners.delete(e)||t.listeners.size>0)return;t.released=!0,t.attempt+=1,Ot(t),It.get(t.connection)===t&&It.delete(t.connection);let r=t.unsubscribe;t.unsubscribe=null,r&&zn(r),t.pending||Lt(t)}function Fo(t){let e={connection:t,listeners:new Map,state:{snapshot:null,error:null},epoch:0,attempt:0,unsubscribe:null,pending:!1,released:!1,retries:0,retryTimer:void 0,onReady:()=>{e.released||e.unsubscribe||(e.pending=!1,e.retries=0,_r(e))},onDisconnected:()=>{e.epoch+=1,e.attempt+=1,e.unsubscribe=null,e.pending=!1,Ot(e),e.released&&Lt(e)}};return e}function jn(t,e){let r=++Mo,i=It.get(t);i?(i.listeners.set(r,e),(i.state.snapshot||i.state.error)&&Bn(e,i.state)):(i=Fo(t),It.set(t,i),i.listeners.set(r,e),t.addEventListener("ready",i.onReady),t.addEventListener("disconnected",i.onDisconnected),_r(i));let n=i,o=!0;return()=>{o&&(o=!1,Do(n,r))}}var Mt=class{snapshot=null;error=null;_host;_connection=null;_unsubscribe=null;_hostConnected=!1;constructor(e){this._host=e,e.addController(this)}setConnection(e){e!==this._connection&&(this._release(),this._connection=e,this.snapshot=null,this.error=null,this._hostConnected&&this._subscribe(),this._host.requestUpdate())}hostConnected(){this._hostConnected=!0,this._subscribe()}hostDisconnected(){this._hostConnected=!1,this._release()}_subscribe(){!this._connection||this._unsubscribe||(this._unsubscribe=jn(this._connection,e=>{this.snapshot=e.snapshot??this.snapshot,this.error=e.error,this._host.requestUpdate()}))}_release(){let e=this._unsubscribe;this._unsubscribe=null,e?.()}};var Je=class extends Y{static properties={_actionError:{state:!0}};_snapshots=new Mt(this);_hass=void 0;_hassKey=null;_locale=null;_localeKey="";constructor(){super(),this._actionError=null}get hass(){return this._hass}set hass(e){this._hass=e,this._snapshots.setConnection(e?.connection??null),this.toggleAttribute("dark",e?.themes?.darkMode===!0);let r=JSON.stringify([e?.language,e?.locale?.language,e?.locale?.time_format,e?.locale?.time_zone,e?.config?.time_zone,e?.user?.is_admin,e?.themes?.darkMode]);r!==this._hassKey&&(this._hassKey=r,this.requestUpdate()),this.hassChanged()}hassChanged(){}get snapshot(){return this._snapshots.snapshot}get locale(){let e=this._snapshots.snapshot?.settings.time_zone,r=`${this._hassKey??""}|${e??""}`;return(!this._locale||r!==this._localeKey)&&(this._locale=Ae(this._hass,e),this._localeKey=r),this._locale}async callService(e,r,i){let n=this._hass;if(!n)return!1;this._actionError=null;try{return await te(n,e,r),!0}catch(o){return this._actionError=p(i,{message:q(o)}),!1}}renderBanners(){let{snapshot:e,error:r}=this._snapshots;return!r&&!this._actionError?u:l`<div class="banners">
      ${r?l`<div class="alert ${e?"warning":"error"}" role="alert">
            <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              ${p(e?s.refreshError:s.loadError,{message:r})}
            </span>
          </div>`:u}
      ${this._actionError?l`<div class="alert error" role="alert">
            <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
            <span class="grow">${this._actionError}</span>
            <button
              type="button"
              class="icon-btn"
              aria-label=${s.dismissMessage}
              title=${s.dismissMessage}
              @click=${this._dismissActionError}
            >
              <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
            </button>
          </div>`:u}
    </div>`}renderLoading(){return this._snapshots.error?u:l`<p class="empty" role="status">${s.loading}</p>`}showActionError(e){this._actionError=e}_dismissActionError(){this._actionError=null}},Le=class extends Je{static properties={_busyParcels:{state:!0},_filter:{state:!0}};_focusedParcel=null;_focusedReturn=null;constructor(){super(),this._busyParcels=new Set,this._filter=Pt()}connectedCallback(){super.connectedCallback(),this._filter=Pt(),window.addEventListener(Et,this._onFilterEvent),window.addEventListener("storage",this._onStorage),window.addEventListener("location-changed",this._onLocationChanged),window.addEventListener("popstate",this._onLocationChanged)}disconnectedCallback(){super.disconnectedCallback(),window.removeEventListener(Et,this._onFilterEvent),window.removeEventListener("storage",this._onStorage),window.removeEventListener("location-changed",this._onLocationChanged),window.removeEventListener("popstate",this._onLocationChanged)}setFilter(e){this._filter=e,Nn(e)}filterParcels(e,r){let i=this._filter;if(i==="all")return r;let n={today:e.settings.today,timeZone:e.settings.time_zone};return r.filter(o=>Dn(o,i,n))}filterReturns(e,r){let i=this._filter;if(i==="all")return r;let n={today:e.settings.today};return r.filter(o=>Fn(o,i,n))}_candidates=null;possiblyFor(e){let r=this.snapshot;if(!r)return null;this._candidates?.snapshot!==r&&(this._candidates={snapshot:r,map:ji(r.merge_suggestions)});let i=this._candidates.map,n=new Set(e.map(a=>a.id)),o=new Map;for(let a of e)for(let c of i.get(a.id)??[])n.has(c.id)||o.set(c.id,c);return o.size?tn([...o.values()]):null}_onFilterEvent=e=>{let r=e.detail;fr(r)&&(this._filter=r)};_onStorage=e=>{(e.key===null||e.key===At)&&(this._filter=Pt())};_onLocationChanged=()=>{this._openLinked()};_openLinked(){let e=this.snapshot;if(!e||!this.isConnected)return;let{pathname:r,search:i,hash:n}=window.location,o=Ln(i);if(o===i)return;window.history.replaceState(window.history.state,"",`${r}${o}${n}`);let a=In(i);if(a?.kind==="parcel"){let c=e.parcels.find(d=>d.id===a.id);c&&this.openDetails(c,null)}else if(a?.kind==="return"){let c=e.returns.find(d=>d.id===a.id);c&&this.openReturn(c,null)}}willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement,i=r instanceof HTMLElement?r.closest(".chip"):null;this._focusedParcel=i?.dataset.parcelId??null,this._focusedReturn=i?.dataset.returnId??null}updated(e){super.updated(e),this._restoreFocus(),this._openLinked()}_restoreFocus(){let e=this._focusedParcel,r=this._focusedReturn;if(this._focusedParcel=null,this._focusedReturn=null,this.shadowRoot?.activeElement||!br())return;let i=e!==null?dr(e):r!==null?ur(r):null;i&&this.renderRoot.querySelector(i)?.focus()}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback], button.chip-main")}openDetails=(e,r)=>{this.renderRoot.querySelector("parcels-details-dialog")?.open(e.id,()=>{(r?.isConnected?r:this.renderRoot.querySelector(dr(e.id))??this.focusFallback())?.focus()})};openReturn=(e,r)=>{this.renderRoot.querySelector("parcels-return-dialog")?.open(e.id,()=>{(r?.isConnected?r:this.renderRoot.querySelector(ur(e.id))??this.focusFallback())?.focus()})};undoMerge=e=>{this._parcelAction(e.id,"undo_merge",{parcel_id:e.id},s.undoFailed)};keepMerge=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_merge:!0},s.keepFailed)};undoInferred=e=>{this._parcelAction(e.id,"undo_delivery",{parcel_id:e.id},s.undoInferredFailed)};keepInferred=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_delivery:!0},s.keepInferredFailed)};renderDetailsDialog(){return l`<parcels-details-dialog
      .hass=${this.hass}
      .snapshot=${this.snapshot}
      .locale=${this.locale}
      @parcels-error=${this._onDialogError}
      @parcels-open-return=${this._onOpenReturn}
    ></parcels-details-dialog>`}renderReturnDialog(){return l`<parcels-return-dialog
      .hass=${this.hass}
      .snapshot=${this.snapshot}
      .locale=${this.locale}
      @parcels-error=${this._onDialogError}
      @parcels-open-parcel=${this._onOpenParcel}
    ></parcels-return-dialog>`}_opener(){let e=this.shadowRoot?.activeElement;return e instanceof HTMLElement?e:this.focusFallback()}_onOpenParcel(e){let r=this.snapshot?.parcels.find(n=>n.id===e.detail),i=this._opener();r&&i&&this.openDetails(r,i)}_onOpenReturn(e){let r=this.snapshot?.returns.find(n=>n.id===e.detail),i=this._opener();r&&i&&this.openReturn(r,i)}async _parcelAction(e,r,i,n){if(!this._busyParcels.has(e)){this._busyParcels=new Set([...this._busyParcels,e]);try{await this.callService(r,i,n)}finally{let o=new Set(this._busyParcels);o.delete(e),this._busyParcels=o}}}_onDialogError(e){this.showActionError(e.detail)}};function br(){let t=document.activeElement;return!t||t===document.body}function vr(t){if(typeof t!="object"||t===null||Array.isArray(t))throw new Error(s.configInvalid);return t}function yr(t){let e=t.title;if(e!=null){if(typeof e!="string")throw new Error(s.configTitle);return e.trim()}}function wr(t){return typeof t.type=="string"?t.type:""}function $r(t){let e=vr(t),r=e.show_archived??!0;if(typeof r!="boolean")throw new Error(s.configShowArchived);return{type:wr(e),title:yr(e),show_archived:r}}function kr(t){let e=vr(t);return{type:wr(e),title:yr(e)}}function xr(t){let e=vr(t);return{type:wr(e),title:yr(e)}}function Oe(t,e){return t===void 0?e:t||null}function Ho(t,e){let r=E(t.status_time,e.timeZone);switch(t.status){case"cancelled":return null;case"delivered":{let n=E(t.delivered_at,e.timeZone)??r;return n?{kind:"delivered",from:n,to:n}:null}case"returned":return r?{kind:"returned",from:r,to:r}:null;case"ready_for_pickup":{let n=r??e.today;return{kind:"pickup",from:n,to:gi(n,e.today)}}default:break}let i=P(t);return i?{kind:"eta",from:i.start,to:i.end}:(t.status==="attempted"||t.status==="exception")&&r?{kind:"status",from:r,to:r}:null}function Sr(t){return t.type==="parcel"?t.parcel.id:`return:${t.ret.id}`}function Kn(t){return t.window_start??t.window_end??"~"}function Xe(t,e){return t<e?-1:t>e?1:0}function Uo(t,e){return Xe(Kn(t.parcel),Kn(e.parcel))||Xe(M(t.parcel).toLowerCase(),M(e.parcel).toLowerCase())||Xe(t.parcel.id,e.parcel.id)}function Bo(t,e){return Xe(ke(t.ret).toLowerCase(),ke(e.ret).toLowerCase())||Xe(t.ret.id,e.ret.id)}function zo(t,e){let r=t.startCol-e.startCol||e.endCol-e.startCol-(t.endCol-t.startCol)||(t.type===e.type?0:t.type==="parcel"?-1:1);return r||(t.type==="parcel"&&e.type==="parcel"?Uo(t,e):t.type==="return"&&e.type==="return"?Bo(t,e):0)}function Wn(t,e,r,i,n=[]){let o=fi(e),a=re(e,6),c=[];for(let h of t){if(h.archived&&!i.showArchived)continue;let _=Ho(h,r);!_||$(_.to,e)<0||$(_.from,a)>0||c.push({type:"parcel",parcel:h,members:[h],placement:_,startCol:Math.max(0,le(e,_.from)),endCol:Math.min(6,le(e,_.to)),continuesBefore:$(_.from,e)<0,continuesAfter:$(_.to,a)>0,lane:0})}let d=or(c,h=>ar(h.parcel,h.placement.kind,h.placement.from,h.placement.to)).map(h=>({...h.reduce((f,v)=>Pe(v.parcel,f.parcel)<0?v:f),members:h.map(f=>f.parcel).sort(Pe)}));for(let h of n){if(h.archived&&!i.showArchived||$(h.day,e)<0||$(h.day,a)>0)continue;let _=le(e,h.day);d.push({type:"return",ret:h,day:h.day,startCol:_,endCol:_,continuesBefore:!1,continuesAfter:!1,lane:0})}d.sort(zo);let m=[];for(let h of d){let _=m.findIndex(f=>f<h.startCol);_===-1&&(_=m.length),m[_]=h.endCol,h.lane=_}let g=o.map((h,_)=>d.filter(f=>f.startCol<=_&&_<=f.endCol).sort((f,v)=>f.lane-v.lane));return{start:e,end:a,days:o,items:d,lanes:m.length,perDay:g,busy:g.map(h=>h.length>0)}}var jo=600,Ko=616,Wo={weekday:"short"},qo={day:"numeric"},Go={weekday:"long",day:"numeric",month:"long"},Vo={weekday:"long",day:"numeric",month:"short"},Rr=class extends Le{static properties={_config:{state:!0},_weekOffset:{state:!0},_narrow:{state:!0},_refreshing:{state:!0}};static styles=[W,_t,R`
      .heading {
        flex: 1 1 12rem;
        min-width: 0;
      }
      .range {
        margin: 0;
        font-size: 0.875rem;
        color: var(--secondary-text-color, #727272);
      }
      .title + .range {
        margin-top: 2px;
      }
      .controls {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 4px 8px;
      }
      .nav {
        display: flex;
        align-items: center;
        gap: 2px;
      }
      .spin {
        animation: spin 1s linear infinite;
      }
      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .spin {
          animation: none;
        }
      }

      .grid {
        display: grid;
        row-gap: 6px;
        padding: 4px 12px 16px;
      }
      .day-bg {
        grid-row: 1 / -1;
        border-inline-start: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
      }
      .day-bg:first-child {
        border-inline-start-color: transparent;
      }
      .day-bg.today {
        border-radius: 8px;
        background: color-mix(in srgb, var(--primary-color, #03a9f4) 8%, transparent);
      }
      .day-head {
        grid-row: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        min-width: 0;
        padding: 6px 0 2px;
        font-size: 0.75rem;
        color: var(--secondary-text-color, #727272);
      }
      .day-head .dow {
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .day-head .dom {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 28px;
        height: 28px;
        border-radius: 14px;
        color: var(--primary-text-color, #212121);
        font-size: 0.9375rem;
        font-weight: 500;
      }
      .day-head.today .dow {
        color: var(--primary-color, #03a9f4);
        font-weight: 600;
      }
      .day-head.today .dom {
        background: var(--primary-color, #03a9f4);
        color: var(--text-primary-color, #fff);
      }
      .grid .chip {
        align-self: start;
        margin: 0 3px;
      }
      .grid .chip.cont-before {
        margin-inline-start: 0;
      }
      .grid .chip.cont-after {
        margin-inline-end: 0;
      }
      .week-empty {
        grid-column: 1 / -1;
        grid-row: 2;
        margin: 0;
        padding: 16px 0;
        color: var(--secondary-text-color, #727272);
        text-align: center;
      }
      .week-empty.stacked {
        padding: 8px 16px;
      }
      .filters {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        padding: 0 16px 8px;
      }
      .filter-btn {
        min-height: 32px;
        padding: 0 12px;
        border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
        border-radius: 16px;
        background: transparent;
        color: var(--primary-text-color, #212121);
        font-size: 0.8125rem;
        font-weight: 500;
        cursor: pointer;
      }
      .filter-btn:hover {
        background: color-mix(in srgb, var(--primary-color, #03a9f4) 8%, transparent);
      }
      .filter-btn[aria-pressed="true"] {
        border-color: transparent;
        background: color-mix(in srgb, var(--primary-color, #03a9f4) 18%, transparent);
        color: var(--primary-color, #03a9f4);
      }

      .days {
        display: flex;
        flex-direction: column;
        gap: 2px;
        margin: 0;
        padding: 4px 12px 16px;
        list-style: none;
      }
      .day {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 8px;
        border-radius: 8px;
      }
      .day.compact {
        flex-direction: row;
        flex-wrap: wrap;
        align-items: baseline;
        gap: 2px 8px;
        padding: 4px 8px;
      }
      .day.today {
        background: color-mix(in srgb, var(--primary-color, #03a9f4) 8%, transparent);
      }
      .day-label {
        display: flex;
        align-items: center;
        gap: 6px;
        margin: 0;
        font-size: 0.875rem;
        font-weight: 500;
      }
      .day.compact .day-label {
        font-weight: 400;
        color: var(--secondary-text-color, #727272);
      }
      .day.compact .muted {
        font-size: 0.8125rem;
      }
      .day.today .day-label {
        color: var(--primary-color, #03a9f4);
      }
      .day-chips {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin: 0;
        padding: 0;
        list-style: none;
      }
    `];_resizeObserver=null;_resizeFrame=0;_layoutCache=null;constructor(){super(),this._config=$r({}),this._weekOffset=0,this._narrow=!1,this._refreshing=!1}static getStubConfig(){return{}}setConfig(e){this._config=$r(e)}getCardSize(){let e=this._layout();return e?this._narrow?9+e.perDay.reduce((i,n)=>i+n.length,0):3+Math.max(1,e.lanes):4}getGridOptions(){return{columns:"full",rows:"auto",min_columns:6}}connectedCallback(){super.connectedCallback(),typeof ResizeObserver<"u"&&(this._resizeObserver??=new ResizeObserver(e=>{let r=e[e.length-1]?.contentRect.width??0;cancelAnimationFrame(this._resizeFrame),this._resizeFrame=requestAnimationFrame(()=>this._measure(r))}),this._resizeObserver.observe(this))}disconnectedCallback(){super.disconnectedCallback(),this._resizeObserver?.disconnect(),cancelAnimationFrame(this._resizeFrame)}firstUpdated(e){super.firstUpdated(e),this._measure(this.getBoundingClientRect().width)}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback]")}_measure(e){e<=0||(e<jo?this._narrow=!0:e>=Ko&&(this._narrow=!1))}_monday(e){return re(ze(e.settings.today),7*this._weekOffset)}_layout(){let e=this.snapshot;if(!e)return null;let r=this._monday(e),i=this._config.show_archived,n=this._filter,o=this._layoutCache;if(o&&o.snapshot===e&&o.monday===r&&o.showArchived===i&&o.filter===n)return o.layout;let a=Wn(this.filterParcels(e,e.parcels),r,{today:e.settings.today,timeZone:e.settings.time_zone},{showArchived:i},this.filterReturns(e,e.returns));return this._layoutCache={snapshot:e,monday:r,showArchived:i,filter:n,layout:a},a}render(){let e=this.snapshot,r=this._layout(),i=Oe(this._config.title,s.defaultWeekTitle),n=r?O(r.start,r.end,this.locale,Si):"";return l`<ha-card>
        <div class="header">
          <div class="heading">
            ${i?l`<h2 class="title">${i}</h2>`:u}
            ${n?l`<p class="range" aria-live="polite">${n}</p>`:u}
          </div>
          <div class="controls">
            <div class="nav" role="group" aria-label=${s.weekNavigation}>
              <button
                type="button"
                class="icon-btn"
                aria-label=${s.previousWeek}
                title=${s.previousWeek}
                @click=${this._previousWeek}
              >
                <ha-icon class="flip" icon="mdi:chevron-left" aria-hidden="true"></ha-icon>
              </button>
              <button type="button" class="btn" title=${s.goToToday} @click=${this._thisWeek}>
                ${s.today}
              </button>
              <button
                type="button"
                class="icon-btn"
                aria-label=${s.nextWeek}
                title=${s.nextWeek}
                @click=${this._nextWeek}
              >
                <ha-icon class="flip" icon="mdi:chevron-right" aria-hidden="true"></ha-icon>
              </button>
            </div>
            <button
              type="button"
              class="icon-btn"
              aria-label=${s.refresh}
              title=${s.refresh}
              aria-disabled=${this._refreshing?"true":"false"}
              @click=${this._refresh}
            >
              <ha-icon
                class=${this._refreshing?"spin":""}
                icon="mdi:refresh"
                aria-hidden="true"
              ></ha-icon>
            </button>
            <button type="button" class="btn" data-focus-fallback @click=${this._openAdd}>
              <ha-icon icon="mdi:plus" aria-hidden="true"></ha-icon>${s.addParcel}
            </button>
          </div>
        </div>
        ${this._renderFilters()} ${this.renderBanners()}
        ${e&&r?this._narrow?this._renderStacked(e,r,n):this._renderGrid(e,r,n):l`<div class="content">${this.renderLoading()}</div>`}
      </ha-card>
      ${this.renderDetailsDialog()} ${this.renderReturnDialog()}
      <parcels-add-dialog
        .hass=${this.hass}
        @parcels-error=${this._onAddError}
      ></parcels-add-dialog>`}_renderGrid(e,r,i){let n=this.locale,o=e.settings.today,a=r.items.length===0,d={"grid-template-columns":r.busy.map(m=>m||a?"minmax(0, 1fr)":"minmax(0, 0.6fr)").join(" "),"grid-template-rows":`auto repeat(${Math.max(1,r.lanes)}, auto)`};return l`<div
      class="grid"
      role="group"
      aria-label=${p(s.weekOf,{range:i})}
      style=${z(d)}
    >
      ${r.days.map((m,g)=>l`<div
            class="day-bg ${m===o?"today":""}"
            style=${z({"grid-column":String(g+1)})}
            aria-hidden="true"
          ></div>`)}
      ${r.days.map((m,g)=>l`<div
            class="day-head ${m===o?"today":""}"
            style=${z({"grid-column":String(g+1)})}
            aria-current=${m===o?"date":u}
          >
            <span class="dow" aria-hidden="true">${H(m,n,Wo)}</span>
            <span class="dom" aria-hidden="true">${H(m,n,qo)}</span>
            <span class="sr-only">${H(m,n,Go)}</span>
          </div>`)}
      ${a?l`<p class="week-empty">${this._emptyText()}</p>`:u}
      ${ee(r.items,Sr,m=>this._chip(m,!1,{"grid-column":`${m.startCol+1} / ${m.endCol+2}`,"grid-row":String(m.lane+2)}))}
    </div>`}_renderStacked(e,r,i){let n=this.locale,o=e.settings.today,a=this._filter!=="all"&&r.items.length===0;return l`${a?l`<p class="week-empty stacked">${this._emptyText()}</p>`:u}
      <ol class="days" aria-label=${p(s.weekOf,{range:i})}>
      ${r.days.map((c,d)=>{let m=r.perDay[d]??[],g=c===o;return l`<li
          class="day ${m.length?"":"compact"} ${g?"today":""}"
          aria-current=${g?"date":u}
        >
          <p class="day-label">
            ${H(c,n,Vo)}${g?l`<span class="badge info">${s.todayTag}</span>`:u}
          </p>
          ${m.length?l`<ul class="day-chips">
                ${ee(m,Sr,h=>l`<li>${this._chip(h,!0,void 0,d)}</li>`)}
              </ul>`:l`<span class="muted">${s.noDeliveriesThisDay}</span>`}
        </li>`})}
    </ol>`}_chip(e,r,i,n){if(e.type==="return")return fn(e.ret,{locale:this.locale,today:this.snapshot?.settings.today??"",position:i,onOpen:this.openReturn});let o=e.continuesBefore&&(!r||n===e.startCol),a=e.continuesAfter&&(!r||n===e.endCol);return kt(e.parcel,{locale:this.locale,placement:e.placement,continuesBefore:o,continuesAfter:a,showRange:r,members:e.members,possibly:this.possiblyFor(e.members),busy:e.members.some(c=>this._busyParcels.has(c.id)),position:i,onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge,onUndoInferred:this.undoInferred,onKeepInferred:this.keepInferred})}_renderFilters(){return l`<div class="filters" role="group" aria-label=${s.filterLabel}>
      ${mr.map(e=>l`<button
            type="button"
            class="filter-btn"
            aria-pressed=${this._filter===e?"true":"false"}
            title=${e==="recent"?s.filterRecentHint:u}
            @click=${()=>this.setFilter(e)}
          >
            ${Ct[e]}
          </button>`)}
    </div>`}_emptyText(){return this._filter==="all"?s.noDeliveriesThisWeek:s.filterEmptyWeek}_previousWeek(){this._weekOffset-=1}_nextWeek(){this._weekOffset+=1}_thisWeek(){this._weekOffset=0}async _refresh(){if(!this._refreshing){this._refreshing=!0;try{await this.callService("refresh",{},s.refreshFailed)}finally{this._refreshing=!1}}}_openAdd(e){let r=e.currentTarget;this.renderRoot.querySelector("parcels-add-dialog")?.open(()=>{r.isConnected&&r.focus()})}_onAddError(e){this.showActionError(e.detail)}};K("parcels-week-card",Rr);Te("parcels-week-card",s.weekCardName,s.weekCardDescription);var Tr=class extends Le{static properties={_config:{state:!0}};static styles=[W,_t,R`
      .list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .content:focus {
        outline: none;
      }
      .filter-note {
        margin: 0 0 8px;
        font-size: 0.875rem;
        color: var(--secondary-text-color, #727272);
      }
    `];_listCache=null;constructor(){super(),this._config=kr({})}static getStubConfig(){return{}}setConfig(e){this._config=kr(e)}getCardSize(){let e=this._list()?.boxes;return e?1+Math.max(1,e.length):3}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}focusFallback(){return this.renderRoot.querySelector("button.chip-main")??this.renderRoot.querySelector(".content")}_list(){let e=this.snapshot;if(!e)return null;let r=this._filter,i=this._listCache;if(i?.snapshot===e&&i.filter===r)return i;let n=Fi(e.parcels),o=this.filterParcels(e,n);return this._listCache={snapshot:e,filter:r,boxes:sn(o),hidden:n.length-o.length},this._listCache}render(){let e=this._list(),r=Oe(this._config.title,s.defaultListTitle);return l`<ha-card>
        ${r?l`<div class="header"><h2 class="title">${r}</h2></div>`:u}
        ${this.renderBanners()}
        <div class="content" tabindex="-1">
          ${e?this._renderList(e.boxes,e.hidden):this.renderLoading()}
        </div>
      </ha-card>
      ${this.renderDetailsDialog()} ${this.renderReturnDialog()}`}_renderFilterNote(e){return e===0||this._filter==="all"?u:l`<p class="filter-note">
      ${p(s.filterNote,{filter:Ct[this._filter]})} ·
      <button type="button" class="link-btn" @click=${this._showAll}>${s.filterShowAll}</button>
    </p>`}_showAll=()=>{this.setFilter("all")};_renderList(e,r){if(!e.length)return l`${this._renderFilterNote(r)}
        <p class="empty">${r>0?s.noUndatedMatch:s.noUndatedParcels}</p>`;let i=this.locale;return l`${this._renderFilterNote(r)}
      <ul class="list">
      ${ee(e,n=>n.parcel.id,({parcel:n,members:o})=>l`<li>
            ${kt(n,{locale:i,showStatus:!0,members:o,possibly:this.possiblyFor(o),busy:o.some(a=>this._busyParcels.has(a.id)),onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge,onUndoInferred:this.undoInferred,onKeepInferred:this.keepInferred})}
          </li>`)}
    </ul>`}};K("parcels-list-card",Tr);Te("parcels-list-card",s.listCardName,s.listCardDescription);function Yo(t,e,r){let i=t.get(e);return i==="pending"||i!==void 0&&i===r}function Nt(t,e,r){if(!e.size)return t;let i=t.filter(n=>!Yo(e,n.id,r));return i.length===t.length?t:i}function Ar(t,e){let r=new Map(t);for(let i of e)r.set(i,"pending");return r}function Er(t,e){let r=new Map(t);for(let i of e)r.delete(i);return r}function Pr(t,e,r,i){let n=new Map(t);for(let o of e)r&&i(o)?n.set(o,r):n.delete(o);return n}function qn(t,e){let r=null;for(let[i,n]of t)n!=="pending"&&n!==e&&(r??=new Map(t),r.delete(i));return r??t}function Gn(t,e){if(t<=0)return null;let r=t===1?s.aiQueueOne:p(s.aiQueueMany,{count:t});if(e===null)return r;let i=Math.max(1,Math.round(e/60));return i<120?p(s.aiQueueMinutes,{queue:r,minutes:i}):p(s.aiQueueHours,{queue:r,hours:Math.round(i/60)})}function Cr(t,e,r){return t<=0?null:t===1?e:p(r,{count:t})}function Vn(t){let e=[Cr(t.added,s.trustAddedOne,s.trustAddedMany),Cr(t.rechecking,s.trustRecheckOne,s.trustRecheckMany),Cr(t.kept,s.trustKeptOne,s.trustKeptMany)].filter(r=>r!==null);return e.length?p(s.trustDoneWith,{domain:t.domain,parts:e.join(", ")}):p(s.trustDone,{domain:t.domain})}function Yn(t){let e=[[s.checkHeaders,String(t.headers)]];return t.servers.length&&e.push([s.checkServers,t.servers.map(r=>r||s.checkNoServer).join(", ")]),t.originals>0&&e.push([s.checkOriginals,String(t.originals)]),t.used===null?(e.push([s.checkUsed,s.checkUsedNone]),e):(e.push([s.checkUsed,p(s.checkUsedHeader,{n:t.used+1})],["DKIM",t.dkim||s.checkNoResult],["DMARC",t.dmarc||s.checkNoResult],["SPF",t.spf||s.checkNoResult]),e)}function Qn(t){let e=t.subject.trim();return e||(t.removed?s.removedFromParcel:s.noSubject)}var Me=["review","filtered"],Qo=new Set(["not_parcel","unknown"]),Zo={weekday:"short",day:"numeric",month:"short"};function Zn(t){return L(t.received??t.created)??-1/0}function Jn(t){return[...t].sort((e,r)=>Zn(r)-Zn(e)||(e.id<r.id?-1:e.id>r.id?1:0))}function Jo(t){return[...t].sort((e,r)=>(r.day??"").localeCompare(e.day??"")||(e.id<r.id?-1:e.id>r.id?1:0))}function Ir(t,e){if(!t.has(e))return t;let r=new Map(t);return r.delete(e),r}var Lr=class extends Je{static properties={_config:{state:!0},_tab:{state:!0},_editing:{state:!0},_editForm:{state:!0},_editProblem:{state:!0},_busyItems:{state:!0},_itemErrors:{state:!0},_hidden:{state:!0},_confirmClearAll:{state:!0},_confirmTrust:{state:!0},_trustStatus:{state:!0}};static styles=[W,R`
      .tabs {
        display: flex;
        gap: 4px;
        padding: 0 12px;
        border-bottom: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
      }
      .tab {
        min-height: 44px;
        padding: 0 12px;
        border: none;
        border-bottom: 2px solid transparent;
        background: none;
        color: var(--secondary-text-color, #727272);
        font-size: 0.875rem;
        font-weight: 500;
        cursor: pointer;
      }
      .tab:hover {
        color: var(--primary-text-color, #212121);
      }
      .tab[aria-selected="true"] {
        border-bottom-color: var(--primary-color, #03a9f4);
        color: var(--primary-color, #03a9f4);
      }
      .panel {
        padding: 12px 16px 16px;
      }
      .panel:focus-visible {
        outline-offset: -2px;
      }
      .items {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .item {
        padding: 12px;
        border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
        border-radius: 12px;
      }
      .item:focus-visible {
        outline-offset: 0;
      }
      .item-head {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        font-size: 0.875rem;
        color: var(--secondary-text-color, #727272);
        overflow-wrap: anywhere;
      }
      .sender {
        font-weight: 500;
        color: var(--primary-text-color, #212121);
      }
      .subject {
        margin: 4px 0 0;
        font-size: 1rem;
        font-weight: 500;
        line-height: 1.35;
        overflow-wrap: anywhere;
      }
      .meta {
        margin: 4px 0 0;
        font-size: 0.8125rem;
        color: var(--secondary-text-color, #727272);
        overflow-wrap: anywhere;
      }
      .block {
        display: block;
      }
      .section-label {
        margin: 12px 0 4px;
        font-size: 0.8125rem;
        font-weight: 600;
        color: var(--secondary-text-color, #727272);
      }
      .facts {
        display: grid;
        grid-template-columns: minmax(6rem, max-content) minmax(0, 1fr);
        gap: 4px 12px;
        margin: 0;
        font-size: 0.875rem;
      }
      .facts dt {
        color: var(--secondary-text-color, #727272);
      }
      .facts dd {
        margin: 0;
        overflow-wrap: anywhere;
      }
      .facts ul {
        margin: 0;
        padding-inline-start: 18px;
      }
      .edit-form {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-top: 12px;
      }
      .edit-form .alert {
        margin: 0;
      }
      .filtered-hint,
      .queue-hint {
        margin-bottom: 12px;
      }
      .clear-all {
        margin: 0 0 12px;
      }
      .confirm {
        margin-bottom: 12px;
        padding: 12px;
        border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
        border-radius: 12px;
      }
      .confirm p {
        margin: 0;
      }
      .item .confirm {
        margin: 12px 0 0;
      }
      .trust-status .alert {
        margin: 0 0 12px;
      }
      .checks {
        margin-top: 8px;
        font-size: 0.875rem;
      }
      .checks summary {
        padding: 12px 0;
        cursor: pointer;
        color: var(--secondary-text-color, #727272);
      }
      .checks .codes {
        margin: 0;
        padding-inline-start: 20px;
      }
      .candidates {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin: 8px 0 0;
        padding: 0;
        list-style: none;
      }
      .candidate {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px;
        border-radius: 8px;
        background: var(--secondary-background-color, rgba(0, 0, 0, 0.04));
        overflow-wrap: anywhere;
      }
      .candidate .grow {
        flex: 1;
        min-width: 0;
      }
      .subject-lines {
        margin: 4px 0 8px;
        font-size: 0.875rem;
      }
      .items-line {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    `];connectedWhileHidden=!0;_focusedItem=null;_listCache=null;_visibleCache=null;_clearingAll=!1;constructor(){super(),this._config=xr({}),this._tab="review",this._editing=null,this._editForm=Yt(null),this._editProblem=null,this._busyItems=new Set,this._itemErrors=new Map,this._hidden=new Map,this._confirmClearAll=!1,this._confirmTrust=null,this._trustStatus=null}static getStubConfig(){return{}}setConfig(e){this._config=xr(e)}getCardSize(){if(!this._visible())return 0;let e=this._visibleLists();if(!e)return 3;let r=this._tab==="review"?e.review.length+e.suggestions.length:e.filtered.length;return 2+2*Math.max(1,r)}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}hassChanged(){this._syncVisibility()}_visible(){let e=this.snapshot;return e?e.settings.user_is_admin:this.hass?.user?.is_admin===!0}_syncVisibility(){let e=!this._visible();this.hidden!==e&&(this.hidden=e,this.dispatchEvent(new CustomEvent("card-visibility-changed",{bubbles:!0,composed:!0,detail:{value:!e}})))}_lists(){let e=this.snapshot;return e?(this._listCache?.snapshot!==e&&(this._listCache={snapshot:e,review:Jn(e.review),suggestions:Jo(e.merge_suggestions),filtered:Jn(e.filtered)}),this._listCache):null}_visibleLists(){let e=this._lists();if(!e)return null;let r=this._hidden;if(this._visibleCache?.lists!==e||this._visibleCache.hidden!==r){let i=this.snapshot;this._visibleCache={lists:e,hidden:r,visible:{review:Nt(e.review,r,i),suggestions:Nt(e.suggestions,r,i),filtered:Nt(e.filtered,r,i)}}}return this._visibleCache.visible}_listed(e){let r=this._lists();return r?[...r.review,...r.suggestions,...r.filtered].some(i=>i.id===e):!1}willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement,i=r instanceof HTMLElement?r.closest("[data-item-id]"):null;if(i){let o=[...this.renderRoot.querySelectorAll("[data-item-id]")].filter(a=>!a.closest("[hidden]"));this._focusedItem={id:i.dataset.itemId??"",index:o.indexOf(i)}}else this._focusedItem=null;this._hidden=qn(this._hidden,this.snapshot),this._confirmClearAll&&!this._visibleLists()?.filtered.length&&(this._confirmClearAll=!1,r instanceof HTMLElement&&r.closest(".confirm")&&this._focusAfterUpdate("#panel-filtered"));let n=this._lists();if(n){let o=new Set([...n.review,...n.suggestions,...n.filtered].map(a=>a.id));this._editing!==null&&!o.has(this._editing)&&(this._editing=null,this._editProblem=null);for(let a of this._itemErrors.keys())o.has(a)||(this._itemErrors=Ir(this._itemErrors,a))}}updated(e){super.updated(e),this._syncVisibility();let r=this._focusedItem;if(this._focusedItem=null,!r||this.shadowRoot?.activeElement||!br())return;let n=[...this.renderRoot.querySelector(`#panel-${this._tab}`)?.querySelectorAll("[data-item-id]")??[]];(n.find(a=>a.dataset.itemId===r.id)??n[Math.min(Math.max(r.index,0),n.length-1)]??this.renderRoot.querySelector(`#tab-${this._tab}`))?.focus()}render(){if(!this._visible())return u;let e=this._visibleLists(),r=Oe(this._config.title,s.defaultReviewTitle);return l`<ha-card>
      ${r?l`<div class="header"><h2 class="title">${r}</h2></div>`:u}
      ${this.renderBanners()}
      ${e?l`${this._renderTabs(e.review.length+e.suggestions.length,e.filtered.length)}
            <div
              class="panel"
              role="tabpanel"
              id="panel-review"
              aria-labelledby="tab-review"
              tabindex="0"
              ?hidden=${this._tab!=="review"}
            >
              ${this._renderReviewList(e.review,e.suggestions)}
            </div>
            <div
              class="panel"
              role="tabpanel"
              id="panel-filtered"
              aria-labelledby="tab-filtered"
              tabindex="0"
              ?hidden=${this._tab!=="filtered"}
            >
              ${this._renderFilteredList(e.filtered)}
            </div>`:l`<div class="content">${this.renderLoading()}</div>`}
    </ha-card>`}_renderTabs(e,r){let i=n=>p(s.tabCount,{label:n==="review"?s.tabReview:s.tabFiltered,count:n==="review"?e:r});return l`<div
      class="tabs"
      role="tablist"
      aria-label=${s.reviewTabs}
      @keydown=${this._onTabKeyDown}
    >
      ${Me.map(n=>{let o=this._tab===n;return l`<button
          type="button"
          class="tab"
          role="tab"
          id="tab-${n}"
          data-tab=${n}
          aria-selected=${o?"true":"false"}
          aria-controls="panel-${n}"
          tabindex=${o?"0":"-1"}
          @click=${this._onTabClick}
        >
          ${i(n)}
        </button>`})}
    </div>`}_renderReviewList(e,r){let i=this.snapshot?.settings,n=i?Gn(i.ai_queue,i.ai_queue_seconds):null,o=n?l`<p class="hint queue-hint">${n}</p>`:u,a=l`<div class="trust-status" role="status">
      ${this._trustStatus?l`<div class="alert">
            <ha-icon icon="mdi:shield-check-outline" aria-hidden="true"></ha-icon>
            <span class="grow">${this._trustStatus}</span>
            <button
              type="button"
              class="icon-btn"
              aria-label=${s.dismissMessage}
              title=${s.dismissMessage}
              @click=${this._dismissTrustStatus}
            >
              <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
            </button>
          </div>`:u}
    </div>`;return!e.length&&!r.length?l`${a}${o}<p class="empty">${s.emptyReview}</p>`:l`${a}${o}<div class="items">
      ${ee(r,c=>c.id,(c,d)=>this._renderMergeSuggestion(c,d))}
      ${ee(e,c=>c.id,(c,d)=>this._renderReviewItem(c,d))}
    </div>`}_renderMergeSuggestion(e,r){let i=this.locale,o=this._busyItems.has(e.id)?"true":"false",a=`suggestion-subject-${r}`,c=Ve(e.parcel,i),d=vt(e.reason),m=this.snapshot?.settings,g=m?[...e.candidates].sort(tr(e.parcel,{today:m.today,timeZone:m.time_zone})):e.candidates;return l`<article
      class="item"
      tabindex="-1"
      data-item-id=${e.id}
      aria-labelledby=${a}
      aria-busy=${o}
    >
      <div class="item-head">
        <span class="badge warning">${s.possibleDuplicate}</span>
      </div>
      <h3 class="subject" id=${a}>
        ${p(s.suggestionTitle,{parcel:Ee(e.parcel,i).title})}
      </h3>
      <p class="subject-lines">${this._renderLines(e.parcel)}</p>
      ${d?l`<p class="meta">${p(s.reasonIs,{reason:d})}</p>`:u}
      <p class="hint">${s.suggestionHint}</p>
      <ul class="candidates">
        ${g.map(h=>{let _=Ve(h,i);return l`<li class="candidate">
            <span class="grow">${this._renderLines(h)}</span>
            <button
              type="button"
              class="btn"
              aria-label=${p(s.mergeSuggestedLabel,{candidate:_,title:c})}
              aria-disabled=${o}
              @click=${()=>this._command(e.id,"suggestion/accept",{suggestion_id:e.id,parcel_id:h.id})}
            >
              ${s.mergeSuggested}
            </button>
          </li>`})}
      </ul>
      ${this._renderError(e.id)}
      <div class="row-actions">
        <button
          type="button"
          class="btn"
          aria-label=${p(s.keepApartLabel,{title:c})}
          aria-disabled=${o}
          @click=${()=>this._command(e.id,"suggestion/dismiss",{suggestion_id:e.id})}
        >
          ${s.keepApart}
        </button>
      </div>
    </article>`}_renderLines(e){let r=Ee(e,this.locale);return l`<span class="block"><strong>${r.title}</strong> · ${r.when}</span>
      <span class="meta block">${r.carrier}</span>
      ${r.emails?l`<span class="meta block">${r.emails}</span>`:u}
      <span class="meta block items-line">${r.items??r.noItems}</span>`}_renderFilteredList(e){return l`<p class="hint filtered-hint">${s.filteredHint}</p>
      ${e.length?l`${this._renderClearAll()}
            <div class="items">
            ${ee(e,r=>r.id,(r,i)=>this._renderFilteredItem(r,i))}
          </div>`:l`<p class="empty">${s.emptyFiltered}</p>`}`}_renderClearAll(){return this._confirmClearAll?l`<div
      class="confirm"
      role="group"
      aria-labelledby="clear-all-question"
      @keydown=${this._onConfirmKeyDown}
    >
      <p id="clear-all-question">${s.clearAllQuestion}</p>
      <div class="row-actions">
        <button type="button" class="btn danger primary" @click=${this._clearAll}>
          ${s.clearAll}
        </button>
        <button type="button" class="btn" id="clear-all-cancel" @click=${this._cancelClearAll}>
          ${s.cancel}
        </button>
      </div>
    </div>`:l`<div class="row-actions clear-all">
        <button type="button" class="btn" id="clear-all" @click=${this._askClearAll}>
          ${s.clearAll}
        </button>
      </div>`}_renderHead(e,r,i=u){let n=Qn({subject:e.subject,removed:e.removed===!0});return l`<div class="item-head">
        <span class="sender">${e.sender||e.sender_domain}</span>${i}
      </div>
      <h3 class="subject" id=${r}>${n}</h3>`}_renderError(e){let r=this._itemErrors.get(e);return r?l`<div class="alert error" role="alert">
          <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
          <span class="grow">${r}</span>
        </div>`:u}_renderReviewItem(e,r){let i=this.locale,n=this._busyItems.has(e.id),o=this._editing===e.id,a=`review-subject-${r}`,c=e.received??e.created,d=Ei(e.reason),m=[c?p(s.receivedOn,{date:U(c,i)}):"",e.mailbox_owner?p(s.mailboxOf,{owner:e.mailbox_owner}):"",d?p(s.reasonIs,{reason:d}):""].filter(Boolean),g=e.source==="ai"?l`<span class="badge ai" title=${s.aiSuggestionLabel}>
            ${s.aiBadge}<span class="sr-only">, ${s.aiSuggestionLabel}</span>
          </span>`:u;return l`<article
      class="item"
      tabindex="-1"
      data-item-id=${e.id}
      aria-labelledby=${a}
      aria-busy=${n?"true":"false"}
    >
      ${this._renderHead(e,a,g)}
      ${m.length?l`<p class="meta">${m.join(" \xB7 ")}</p>`:u}
      ${e.authenticated?u:l`<div class="alert warning">
            <ha-icon icon="mdi:shield-alert-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              <strong class="block">${s.unverifiedSender}</strong>
              ${e.trusted_sender?p(s.trustedSenderNote,{domain:e.sender_domain||e.sender}):s.unverifiedSenderHint}
            </span>
          </div>`}
      ${e.checks?this._renderChecks(e.checks):u}
      ${e.errors.length?this._renderFailedChecks(e.errors):u}
      ${e.notes.length?this._renderNotes(e.notes):u}
      ${o?this._renderEditForm(e,n):this._renderSuggestion(e.suggestion)}
      ${this._renderError(e.id)} ${o?u:this._renderReviewActions(e,n)}
    </article>`}_renderChecks(e){return l`<details class="checks">
      <summary>${s.senderChecks}</summary>
      <dl class="facts">
        ${Yn(e).map(([r,i])=>l`<dt>${r}</dt><dd>${i}</dd>`)}
      </dl>
    </details>`}_renderFailedChecks(e){return l`<details class="checks">
      <summary>${s.failedChecks}</summary>
      <ul class="codes">
        ${e.map(r=>l`<li><code>${r}</code></li>`)}
      </ul>
    </details>`}_renderNotes(e){return l`<details class="checks">
      <summary>${s.aiNotes}</summary>
      <p class="hint">${s.aiNotesHint}</p>
      <ul class="codes">
        ${e.map(r=>{let i=Pi(r);return l`<li><code>${r}</code>${i?`: ${i}`:u}</li>`})}
      </ul>
    </details>`}_renderSuggestion(e){if(!e)return l`<p class="hint section-label">${s.noSuggestion}</p>`;let r=this.locale,i=P(e),n=[[s.fieldKind,We(e.kind)||null],[s.fieldMerchant,e.merchant],[s.fieldCarrier,x({carrier:e.carrier,carrier_name:null})],[s.fieldTrackingNumbers,e.tracking_numbers.join(", ")||null],[s.fieldOrderNumbers,e.order_numbers.join(", ")||null],[s.fieldReference,e.reference],[e.kind==="customer_return"?s.pickup:s.expected,i?O(i.start,i.end,r,Zo):null],[s.timeWindow,ie(e.window_start,e.window_end,r)],[s.pickupPoint,e.pickup_point],[s.pickupCode,e.pickup_code],[s.items,e.items.length?l`<ul>
              ${e.items.map(o=>l`<li>${o}</li>`)}
            </ul>`:null]];return l`<p class="section-label">${s.suggestion}</p>
      <dl class="facts">
        ${n.filter(([,o])=>o!==null&&o!=="").map(([o,a])=>l`<dt>${o}</dt><dd>${a}</dd>`)}
      </dl>`}_renderReviewActions(e,r){let i=r?"true":"false",n=e.sender_domain||e.sender;return l`<div class="row-actions">
      ${e.suggestion?l`<button
            type="button"
            class="btn primary"
            aria-disabled=${i}
            @click=${()=>this._accept(e)}
          >
            ${s.accept}
          </button>`:u}
      <button
        type="button"
        class="btn"
        data-edit
        aria-disabled=${i}
        @click=${()=>this._startEdit(e)}
      >
        ${s.edit}
      </button>
      <button
        type="button"
        class="btn"
        aria-disabled=${i}
        @click=${()=>this._command(e.id,"review/dismiss",{review_id:e.id})}
      >
        ${s.dismiss}
      </button>
      ${e.trusted_sender||e.fill?u:l`<button
            type="button"
            class="btn"
            data-trust
            title=${p(s.trustSenderHint,{domain:n})}
            aria-disabled=${i}
            aria-expanded=${e.authenticated?u:this._confirmTrust===e.id?"true":"false"}
            @click=${()=>this._askTrust(e)}
          >
            ${s.trustSender}
          </button>`}
      <button
        type="button"
        class="btn danger"
        title=${p(s.ignoreSenderHint,{domain:n})}
        aria-disabled=${i}
        @click=${()=>this._command(e.id,"review/ignore_sender",{review_id:e.id})}
      >
        ${s.ignoreSender}
      </button>
    </div>
    ${this._confirmTrust===e.id?this._renderTrustConfirm(e,n,r):u}`}_renderTrustConfirm(e,r,i){let n=`trust-question-${e.id}`;return l`<div
      class="confirm"
      role="group"
      aria-labelledby=${n}
      @keydown=${o=>this._onTrustKeyDown(o,e.id)}
    >
      <p id=${n}>${p(s.trustQuestion,{domain:r})}</p>
      <div class="row-actions">
        <button
          type="button"
          class="btn danger primary"
          aria-disabled=${i?"true":"false"}
          @click=${()=>{this._trust(e)}}
        >
          ${p(s.trustConfirm,{domain:r})}
        </button>
        <button type="button" class="btn" data-trust-cancel @click=${()=>this._cancelTrust(e.id)}>
          ${s.cancel}
        </button>
      </div>
    </div>`}_renderEditForm(e,r){let i=this._editForm,n=this._editProblem,o=Object.keys(pt).filter(d=>!Qo.has(d)||d===i.kind);o.includes(i.kind)||o.unshift(i.kind);let a=ut();i.carrier&&!Object.hasOwn(oe,i.carrier)&&a.unshift({id:i.carrier,name:i.carrier});let c=(d,m,g="text",h)=>{let _=n?.field===d,f=[_?"edit-error":"",h??""].filter(Boolean).join(" ");return l`<label class="field">
        <span class="field-label">${m}</span>
        <input
          type=${g}
          name=${d}
          autocomplete="off"
          .value=${D(i[d])}
          aria-invalid=${_?"true":"false"}
          aria-describedby=${f||u}
          @input=${this._onEditInput}
        />
      </label>`};return l`<form id="edit-form" class="edit-form" novalidate @submit=${this._submitEdit}>
      <div class="form-grid">
        <label class="field">
          <span class="field-label">${s.fieldKind}</span>
          <select name="kind" data-first @change=${this._onEditInput}>
            ${o.map(d=>l`<option value=${d} ?selected=${d===i.kind}>
                  ${We(d)||d}
                </option>`)}
          </select>
        </label>
        ${c("merchant",s.fieldMerchant)}
        <label class="field">
          <span class="field-label">${s.fieldCarrier}</span>
          <select name="carrier" @change=${this._onEditInput}>
            <option value="" ?selected=${i.carrier===""}>${s.carrierUnknown}</option>
            ${a.map(d=>l`<option value=${d.id} ?selected=${d.id===i.carrier}>
                  ${d.name}
                </option>`)}
          </select>
        </label>
        <div class="field">
          ${c("tracking_numbers",s.fieldTrackingNumbers,"text","edit-hint-tracking")}
          <p class="hint" id="edit-hint-tracking">${s.hintList}</p>
        </div>
        <div class="field">
          ${c("order_numbers",s.fieldOrderNumbers,"text","edit-hint-orders")}
          <p class="hint" id="edit-hint-orders">${s.hintList}</p>
        </div>
        ${c("reference",s.fieldReference)}
        ${c("eta_start",s.fieldEtaStart,"date")}
        ${c("eta_end",s.fieldEtaEnd,"date")}
        ${c("window_start",s.fieldWindowStart,"time")}
        ${c("window_end",s.fieldWindowEnd,"time")}
        ${c("pickup_point",s.fieldPickupPoint)}
        ${c("pickup_code",s.fieldPickupCode)}
        <label class="field wide">
          <span class="field-label">${s.fieldItems}</span>
          <textarea
            name="items"
            rows="3"
            .value=${D(i.items)}
            aria-describedby="edit-hint-items"
            @input=${this._onEditInput}
          ></textarea>
          <span class="hint" id="edit-hint-items">${s.hintItems}</span>
        </label>
      </div>
      ${n?l`<div class="alert error" id="edit-error" role="alert">
            <span class="grow">${n.message}</span>
          </div>`:u}
      <div class="row-actions">
        <button type="submit" class="btn primary" aria-disabled=${r?"true":"false"}>
          ${s.acceptWithChanges}
        </button>
        <button type="button" class="btn" @click=${()=>this._cancelEdit(e.id)}>
          ${s.cancel}
        </button>
      </div>
    </form>`}_renderFilteredItem(e,r){let i=`filtered-subject-${r}`,n=e.received??e.created,o=this._busyItems.has(e.id);return l`<article
      class="item"
      tabindex="-1"
      data-item-id=${e.id}
      aria-labelledby=${i}
      aria-busy=${o?"true":"false"}
    >
      ${this._renderHead(e,i)}
      ${n?l`<p class="meta">
            ${p(s.receivedOn,{date:U(n,this.locale)})}
          </p>`:u}
      ${this._renderError(e.id)}
      <div class="row-actions">
        <button
          type="button"
          class="btn"
          aria-disabled=${o?"true":"false"}
          @click=${()=>this._command(e.id,"review/restore",{filtered_id:e.id})}
        >
          ${s.restore}
        </button>
        <button
          type="button"
          class="btn"
          title=${s.clearHint}
          aria-disabled=${o?"true":"false"}
          @click=${()=>this._command(e.id,"filtered/clear",{filtered_id:e.id})}
        >
          ${s.clear}
        </button>
      </div>
    </article>`}_selectTab(e,r){this._tab=e,r&&this.updateComplete.then(()=>this.renderRoot.querySelector(`#tab-${e}`)?.focus())}_onTabClick(e){let r=e.currentTarget.dataset.tab;this._selectTab(r,!1)}_onTabKeyDown(e){let r=Me.indexOf(this._tab),i=getComputedStyle(e.currentTarget).direction==="rtl",n;switch(e.key){case"ArrowRight":n=r+(i?-1:1);break;case"ArrowLeft":n=r+(i?1:-1);break;case"Home":n=0;break;case"End":n=Me.length-1;break;default:return}e.preventDefault();let o=Me[(n+Me.length)%Me.length];o&&this._selectTab(o,!0)}_focusAfterUpdate(e){this.updateComplete.then(()=>this.renderRoot.querySelector(e)?.focus())}_askClearAll(){this._confirmClearAll=!0,this._focusAfterUpdate("#clear-all-cancel")}_cancelClearAll(){this._confirmClearAll=!1,this._focusAfterUpdate("#clear-all")}_onConfirmKeyDown(e){e.key==="Escape"&&(e.preventDefault(),e.stopPropagation(),this._cancelClearAll())}async _clearAll(){let e=this.hass,r=this._visibleLists()?.filtered.map(i=>i.id)??[];if(!(!e||this._clearingAll||!r.length)){this._clearingAll=!0,this._confirmClearAll=!1,this._hidden=Ar(this._hidden,r),this._focusAfterUpdate("#panel-filtered");try{await j(e,"filtered/clear_all"),this._hidden=Pr(this._hidden,r,this.snapshot,i=>this._listed(i))}catch(i){this._hidden=Er(this._hidden,r),this.showActionError(p(s.actionFailed,{message:q(i)}))}finally{this._clearingAll=!1}}}_focusInItem(e,r){this.updateComplete.then(()=>{let i=this.renderRoot.querySelector(`[data-item-id="${CSS.escape(e)}"]`);(i?.querySelector(r)??i)?.focus()})}_startEdit(e){this._busyItems.has(e.id)||(this._editing=e.id,this._editForm=Yt(e.suggestion),this._editProblem=null,this._itemErrors=Ir(this._itemErrors,e.id),this._focusInItem(e.id,"[data-first]"))}_cancelEdit(e){this._editing=null,this._editProblem=null,this._focusInItem(e,"[data-edit]")}_onEditInput(e){let r=e.currentTarget,i=r.name;this._editForm={...this._editForm,[i]:r.value},this._editProblem=null}_submitEdit(e){e.preventDefault();let r=this._editing;if(r===null||this._busyItems.has(r))return;let i=gt(this._editForm);if(i){this._editProblem=i,this._focusInItem(r,`[name="${i.field}"]`);return}this._command(r,"review/accept",{review_id:r,overrides:wi(this._editForm)},{onSuccess:()=>{this._editing===r&&(this._editing=null)}})}_accept(e){this._command(e.id,"review/accept",{review_id:e.id})}_askTrust(e){if(!this._busyItems.has(e.id)){if(e.authenticated){this._trust(e);return}this._confirmTrust=e.id,this._focusInItem(e.id,"[data-trust-cancel]")}}_cancelTrust(e){this._confirmTrust=null,this._focusInItem(e,"[data-trust]")}_onTrustKeyDown(e,r){e.key==="Escape"&&(e.preventDefault(),e.stopPropagation(),this._cancelTrust(r))}async _trust(e){let r=e.sender_domain||e.sender;this._confirmTrust=null,this._trustStatus=null,this._focusInItem(e.id,"[data-trust]"),await this._command(e.id,"review/trust_sender",{review_id:e.id},{hide:!1,onSuccess:i=>{let n=i??{};this._trustStatus=Vn({domain:n.domain??r,added:n.added??0,rechecking:n.rechecking??0,kept:n.kept??0})}})}_dismissTrustStatus(){this._trustStatus=null}async _command(e,r,i,{hide:n=!0,onSuccess:o}={}){let a=this.hass;if(!(!a||this._busyItems.has(e)||this._hidden.has(e))){this._busyItems=new Set([...this._busyItems,e]),this._itemErrors=Ir(this._itemErrors,e),n&&(this._hidden=Ar(this._hidden,[e]));try{let c=await j(a,r,i);n&&(this._hidden=Pr(this._hidden,[e],this.snapshot,d=>this._listed(d))),o?.(c)}catch(c){this._hidden=Er(this._hidden,[e]);let d=p(s.actionFailed,{message:q(c)});this._listed(e)?this._itemErrors=new Map([...this._itemErrors,[e,d]]):this.showActionError(d)}finally{let c=new Set(this._busyItems);c.delete(e),this._busyItems=c}}}};K("parcels-review-card",Lr);Te("parcels-review-card",s.reviewCardName,s.reviewCardDescription);
/*! Bundled license information:

@lit/reactive-element/css-tag.js:
  (**
   * @license
   * Copyright 2019 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/reactive-element.js:
lit-html/lit-html.js:
lit-element/lit-element.js:
lit-html/directive.js:
lit-html/directives/repeat.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/is-server.js:
  (**
   * @license
   * Copyright 2022 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/directive-helpers.js:
lit-html/directives/live.js:
  (**
   * @license
   * Copyright 2020 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/directives/style-map.js:
lit-html/directives/class-map.js:
  (**
   * @license
   * Copyright 2018 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)
*/
