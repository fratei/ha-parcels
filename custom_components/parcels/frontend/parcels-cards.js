var it=globalThis,nt=it.ShadowRoot&&(it.ShadyCSS===void 0||it.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,Bt=Symbol(),Nr=new WeakMap,He=class{constructor(e,r,i){if(this._$cssResult$=!0,i!==Bt)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=r}get styleSheet(){let e=this.o,r=this.t;if(nt&&e===void 0){let i=r!==void 0&&r.length===1;i&&(e=Nr.get(r)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&Nr.set(r,e))}return e}toString(){return this.cssText}},Dr=t=>new He(typeof t=="string"?t:t+"",void 0,Bt),S=(t,...e)=>{let r=t.length===1?t[0]:e.reduce((i,n,o)=>i+(a=>{if(a._$cssResult$===!0)return a.cssText;if(typeof a=="number")return a;throw Error("Value passed to 'css' function must be a 'css' function result: "+a+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(n)+t[o+1],t[0]);return new He(r,t,Bt)},Fr=(t,e)=>{if(nt)t.adoptedStyleSheets=e.map(r=>r instanceof CSSStyleSheet?r:r.styleSheet);else for(let r of e){let i=document.createElement("style"),n=it.litNonce;n!==void 0&&i.setAttribute("nonce",n),i.textContent=r.cssText,t.appendChild(i)}},jt=nt?t=>t:t=>t instanceof CSSStyleSheet?(e=>{let r="";for(let i of e.cssRules)r+=i.cssText;return Dr(r)})(t):t;var{is:os,defineProperty:as,getOwnPropertyDescriptor:ls,getOwnPropertyNames:ds,getOwnPropertySymbols:cs,getPrototypeOf:us}=Object,st=globalThis,Hr=st.trustedTypes,ps=Hr?Hr.emptyScript:"",hs=st.reactiveElementPolyfillSupport,Ue=(t,e)=>t,zt={toAttribute(t,e){switch(e){case Boolean:t=t?ps:null;break;case Object:case Array:t=t==null?t:JSON.stringify(t)}return t},fromAttribute(t,e){let r=t;switch(e){case Boolean:r=t!==null;break;case Number:r=t===null?null:Number(t);break;case Object:case Array:try{r=JSON.parse(t)}catch{r=null}}return r}},Br=(t,e)=>!os(t,e),Ur={attribute:!0,type:String,converter:zt,reflect:!1,useDefault:!1,hasChanged:Br};Symbol.metadata??=Symbol("metadata"),st.litPropertyMetadata??=new WeakMap;var X=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,r=Ur){if(r.state&&(r.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((r=Object.create(r)).wrapped=!0),this.elementProperties.set(e,r),!r.noAccessor){let i=Symbol(),n=this.getPropertyDescriptor(e,i,r);n!==void 0&&as(this.prototype,e,n)}}static getPropertyDescriptor(e,r,i){let{get:n,set:o}=ls(this.prototype,e)??{get(){return this[r]},set(a){this[r]=a}};return{get:n,set(a){let d=n?.call(this);o?.call(this,a),this.requestUpdate(e,d,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??Ur}static _$Ei(){if(this.hasOwnProperty(Ue("elementProperties")))return;let e=us(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(Ue("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(Ue("properties"))){let r=this.properties,i=[...ds(r),...cs(r)];for(let n of i)this.createProperty(n,r[n])}let e=this[Symbol.metadata];if(e!==null){let r=litPropertyMetadata.get(e);if(r!==void 0)for(let[i,n]of r)this.elementProperties.set(i,n)}this._$Eh=new Map;for(let[r,i]of this.elementProperties){let n=this._$Eu(r,i);n!==void 0&&this._$Eh.set(n,r)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let r=[];if(Array.isArray(e)){let i=new Set(e.flat(1/0).reverse());for(let n of i)r.unshift(jt(n))}else e!==void 0&&r.push(jt(e));return r}static _$Eu(e,r){let i=r.attribute;return i===!1?void 0:typeof i=="string"?i:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,r=this.constructor.elementProperties;for(let i of r.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Fr(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,r,i){this._$AK(e,i)}_$ET(e,r){let i=this.constructor.elementProperties.get(e),n=this.constructor._$Eu(e,i);if(n!==void 0&&i.reflect===!0){let o=(i.converter?.toAttribute!==void 0?i.converter:zt).toAttribute(r,i.type);this._$Em=e,o==null?this.removeAttribute(n):this.setAttribute(n,o),this._$Em=null}}_$AK(e,r){let i=this.constructor,n=i._$Eh.get(e);if(n!==void 0&&this._$Em!==n){let o=i.getPropertyOptions(n),a=typeof o.converter=="function"?{fromAttribute:o.converter}:o.converter?.fromAttribute!==void 0?o.converter:zt;this._$Em=n;let d=a.fromAttribute(r,o.type);this[n]=d??this._$Ej?.get(n)??d,this._$Em=null}}requestUpdate(e,r,i,n=!1,o){if(e!==void 0){let a=this.constructor;if(n===!1&&(o=this[e]),i??=a.getPropertyOptions(e),!((i.hasChanged??Br)(o,r)||i.useDefault&&i.reflect&&o===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,i))))return;this.C(e,r,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,r,{useDefault:i,reflect:n,wrapped:o},a){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??r??this[e]),o!==!0||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||i||(r=void 0),this._$AL.set(e,r)),n===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(r){Promise.reject(r)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[n,o]of this._$Ep)this[n]=o;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[n,o]of i){let{wrapped:a}=o,d=this[n];a!==!0||this._$AL.has(n)||d===void 0||this.C(n,void 0,o,d)}}let e=!1,r=this._$AL;try{e=this.shouldUpdate(r),e?(this.willUpdate(r),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(r)):this._$EM()}catch(i){throw e=!1,this._$EM(),i}e&&this._$AE(r)}willUpdate(e){}_$AE(e){this._$EO?.forEach(r=>r.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(r=>this._$ET(r,this[r])),this._$EM()}updated(e){}firstUpdated(e){}};X.elementStyles=[],X.shadowRootOptions={mode:"open"},X[Ue("elementProperties")]=new Map,X[Ue("finalized")]=new Map,hs?.({ReactiveElement:X}),(st.reactiveElementVersions??=[]).push("2.1.2");var Wt=globalThis,jr=t=>t,ot=Wt.trustedTypes,zr=ot?ot.createPolicy("lit-html",{createHTML:t=>t}):void 0,qt="$lit$",ee=`lit$${Math.random().toFixed(9).slice(2)}$`,Gt="?"+ee,ms=`<${Gt}>`,_e=document,je=()=>_e.createComment(""),ze=t=>t===null||typeof t!="object"&&typeof t!="function",Vt=Array.isArray,Yr=t=>Vt(t)||typeof t?.[Symbol.iterator]=="function",Kt=`[ 	
\f\r]`,Be=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Kr=/-->/g,Wr=/>/g,fe=RegExp(`>|${Kt}(?:([^\\s"'>=/]+)(${Kt}*=${Kt}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),qr=/'/g,Gr=/"/g,Qr=/^(?:script|style|textarea|title)$/i,Yt=t=>(e,...r)=>({_$litType$:t,strings:e,values:r}),l=Yt(1),da=Yt(2),ca=Yt(3),$=Symbol.for("lit-noChange"),c=Symbol.for("lit-nothing"),Vr=new WeakMap,ge=_e.createTreeWalker(_e,129);function Zr(t,e){if(!Vt(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return zr!==void 0?zr.createHTML(e):e}var Jr=(t,e)=>{let r=t.length-1,i=[],n,o=e===2?"<svg>":e===3?"<math>":"",a=Be;for(let d=0;d<r;d++){let u=t[d],m,g,h=-1,_=0;for(;_<u.length&&(a.lastIndex=_,g=a.exec(u),g!==null);)_=a.lastIndex,a===Be?g[1]==="!--"?a=Kr:g[1]!==void 0?a=Wr:g[2]!==void 0?(Qr.test(g[2])&&(n=RegExp("</"+g[2],"g")),a=fe):g[3]!==void 0&&(a=fe):a===fe?g[0]===">"?(a=n??Be,h=-1):g[1]===void 0?h=-2:(h=a.lastIndex-g[2].length,m=g[1],a=g[3]===void 0?fe:g[3]==='"'?Gr:qr):a===Gr||a===qr?a=fe:a===Kr||a===Wr?a=Be:(a=fe,n=void 0);let f=a===fe&&t[d+1].startsWith("/>")?" ":"";o+=a===Be?u+ms:h>=0?(i.push(m),u.slice(0,h)+qt+u.slice(h)+ee+f):u+ee+(h===-2?d:f)}return[Zr(t,o+(t[r]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),i]},Ke=class t{constructor({strings:e,_$litType$:r},i){let n;this.parts=[];let o=0,a=0,d=e.length-1,u=this.parts,[m,g]=Jr(e,r);if(this.el=t.createElement(m,i),ge.currentNode=this.el.content,r===2||r===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(n=ge.nextNode())!==null&&u.length<d;){if(n.nodeType===1){if(n.hasAttributes())for(let h of n.getAttributeNames())if(h.endsWith(qt)){let _=g[a++],f=n.getAttribute(h).split(ee),v=/([.?@])?(.*)/.exec(_);u.push({type:1,index:o,name:v[2],strings:f,ctor:v[1]==="."?lt:v[1]==="?"?dt:v[1]==="@"?ct:ve}),n.removeAttribute(h)}else h.startsWith(ee)&&(u.push({type:6,index:o}),n.removeAttribute(h));if(Qr.test(n.tagName)){let h=n.textContent.split(ee),_=h.length-1;if(_>0){n.textContent=ot?ot.emptyScript:"";for(let f=0;f<_;f++)n.append(h[f],je()),ge.nextNode(),u.push({type:2,index:++o});n.append(h[_],je())}}}else if(n.nodeType===8)if(n.data===Gt)u.push({type:2,index:o});else{let h=-1;for(;(h=n.data.indexOf(ee,h+1))!==-1;)u.push({type:7,index:o}),h+=ee.length-1}o++}}static createElement(e,r){let i=_e.createElement("template");return i.innerHTML=e,i}};function be(t,e,r=t,i){if(e===$)return e;let n=i!==void 0?r._$Co?.[i]:r._$Cl,o=ze(e)?void 0:e._$litDirective$;return n?.constructor!==o&&(n?._$AO?.(!1),o===void 0?n=void 0:(n=new o(t),n._$AT(t,r,i)),i!==void 0?(r._$Co??=[])[i]=n:r._$Cl=n),n!==void 0&&(e=be(t,n._$AS(t,e.values),n,i)),e}var at=class{constructor(e,r){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=r}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:r},parts:i}=this._$AD,n=(e?.creationScope??_e).importNode(r,!0);ge.currentNode=n;let o=ge.nextNode(),a=0,d=0,u=i[0];for(;u!==void 0;){if(a===u.index){let m;u.type===2?m=new Ae(o,o.nextSibling,this,e):u.type===1?m=new u.ctor(o,u.name,u.strings,this,e):u.type===6&&(m=new ut(o,this,e)),this._$AV.push(m),u=i[++d]}a!==u?.index&&(o=ge.nextNode(),a++)}return ge.currentNode=_e,n}p(e){let r=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(e,i,r),r+=i.strings.length-2):i._$AI(e[r])),r++}},Ae=class t{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,r,i,n){this.type=2,this._$AH=c,this._$AN=void 0,this._$AA=e,this._$AB=r,this._$AM=i,this.options=n,this._$Cv=n?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,r=this._$AM;return r!==void 0&&e?.nodeType===11&&(e=r.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,r=this){e=be(this,e,r),ze(e)?e===c||e==null||e===""?(this._$AH!==c&&this._$AR(),this._$AH=c):e!==this._$AH&&e!==$&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):Yr(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==c&&ze(this._$AH)?this._$AA.nextSibling.data=e:this.T(_e.createTextNode(e)),this._$AH=e}$(e){let{values:r,_$litType$:i}=e,n=typeof i=="number"?this._$AC(e):(i.el===void 0&&(i.el=Ke.createElement(Zr(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===n)this._$AH.p(r);else{let o=new at(n,this),a=o.u(this.options);o.p(r),this.T(a),this._$AH=o}}_$AC(e){let r=Vr.get(e.strings);return r===void 0&&Vr.set(e.strings,r=new Ke(e)),r}k(e){Vt(this._$AH)||(this._$AH=[],this._$AR());let r=this._$AH,i,n=0;for(let o of e)n===r.length?r.push(i=new t(this.O(je()),this.O(je()),this,this.options)):i=r[n],i._$AI(o),n++;n<r.length&&(this._$AR(i&&i._$AB.nextSibling,n),r.length=n)}_$AR(e=this._$AA.nextSibling,r){for(this._$AP?.(!1,!0,r);e!==this._$AB;){let i=jr(e).nextSibling;jr(e).remove(),e=i}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},ve=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,r,i,n,o){this.type=1,this._$AH=c,this._$AN=void 0,this.element=e,this.name=r,this._$AM=n,this.options=o,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=c}_$AI(e,r=this,i,n){let o=this.strings,a=!1;if(o===void 0)e=be(this,e,r,0),a=!ze(e)||e!==this._$AH&&e!==$,a&&(this._$AH=e);else{let d=e,u,m;for(e=o[0],u=0;u<o.length-1;u++)m=be(this,d[i+u],r,u),m===$&&(m=this._$AH[u]),a||=!ze(m)||m!==this._$AH[u],m===c?e=c:e!==c&&(e+=(m??"")+o[u+1]),this._$AH[u]=m}a&&!n&&this.j(e)}j(e){e===c?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},lt=class extends ve{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===c?void 0:e}},dt=class extends ve{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==c)}},ct=class extends ve{constructor(e,r,i,n,o){super(e,r,i,n,o),this.type=5}_$AI(e,r=this){if((e=be(this,e,r,0)??c)===$)return;let i=this._$AH,n=e===c&&i!==c||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,o=e!==c&&(i===c||n);n&&this.element.removeEventListener(this.name,this,i),o&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},ut=class{constructor(e,r,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=r,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){be(this,e)}},Xr={M:qt,P:ee,A:Gt,C:1,L:Jr,R:at,D:Yr,V:be,I:Ae,H:ve,N:dt,U:ct,B:lt,F:ut},fs=Wt.litHtmlPolyfillSupport;fs?.(Ke,Ae),(Wt.litHtmlVersions??=[]).push("3.3.3");var ei=(t,e,r)=>{let i=r?.renderBefore??e,n=i._$litPart$;if(n===void 0){let o=r?.renderBefore??null;i._$litPart$=n=new Ae(e.insertBefore(je(),o),o,void 0,r??{})}return n._$AI(t),n};var Qt=globalThis,Q=class extends X{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let r=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=ei(r,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return $}};Q._$litElement$=!0,Q.finalized=!0,Qt.litElementHydrateSupport?.({LitElement:Q});var gs=Qt.litElementPolyfillSupport;gs?.({LitElement:Q});(Qt.litElementVersions??=[]).push("4.2.2");var L={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},ae=t=>(...e)=>({_$litDirective$:t,values:e}),Z=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,r,i){this._$Ct=e,this._$AM=r,this._$Ci=i}_$AS(e,r){return this.update(e,r)}update(e,r){return this.render(...r)}};var{I:_s}=Xr,ti=t=>t;var ii=t=>t.strings===void 0,ri=()=>document.createComment(""),Ce=(t,e,r)=>{let i=t._$AA.parentNode,n=e===void 0?t._$AB:e._$AA;if(r===void 0){let o=i.insertBefore(ri(),n),a=i.insertBefore(ri(),n);r=new _s(o,a,t,t.options)}else{let o=r._$AB.nextSibling,a=r._$AM,d=a!==t;if(d){let u;r._$AQ?.(t),r._$AM=t,r._$AP!==void 0&&(u=t._$AU)!==a._$AU&&r._$AP(u)}if(o!==n||d){let u=r._$AA;for(;u!==o;){let m=ti(u).nextSibling;ti(i).insertBefore(u,n),u=m}}}return r},le=(t,e,r=t)=>(t._$AI(e,r),t),bs={},pt=(t,e=bs)=>t._$AH=e,ni=t=>t._$AH,ht=t=>{t._$AR(),t._$AA.remove()};var si=(t,e,r)=>{let i=new Map;for(let n=e;n<=r;n++)i.set(t[n],n);return i},te=ae(class extends Z{constructor(t){if(super(t),t.type!==L.CHILD)throw Error("repeat() can only be used in text expressions")}dt(t,e,r){let i;r===void 0?r=e:e!==void 0&&(i=e);let n=[],o=[],a=0;for(let d of t)n[a]=i?i(d,a):a,o[a]=r(d,a),a++;return{values:o,keys:n}}render(t,e,r){return this.dt(t,e,r).values}update(t,[e,r,i]){let n=ni(t),{values:o,keys:a}=this.dt(e,r,i);if(!Array.isArray(n))return this.ut=a,o;let d=this.ut??=[],u=[],m,g,h=0,_=n.length-1,f=0,v=o.length-1;for(;h<=_&&f<=v;)if(n[h]===null)h++;else if(n[_]===null)_--;else if(d[h]===a[f])u[f]=le(n[h],o[f]),h++,f++;else if(d[_]===a[v])u[v]=le(n[_],o[v]),_--,v--;else if(d[h]===a[v])u[v]=le(n[h],o[v]),Ce(t,u[v+1],n[h]),h++,v--;else if(d[_]===a[f])u[f]=le(n[_],o[f]),Ce(t,n[h],n[_]),_--,f++;else if(m===void 0&&(m=si(a,f,v),g=si(d,h,_)),m.has(d[h]))if(m.has(d[_])){let I=g.get(a[f]),R=I!==void 0?n[I]:null;if(R===null){let oe=Ce(t,n[h]);le(oe,o[f]),u[f]=oe}else u[f]=le(R,o[f]),Ce(t,n[h],R),n[I]=null;f++}else ht(n[_]),_--;else ht(n[h]),h++;for(;f<=v;){let I=Ce(t,u[v+1]);le(I,o[f]),u[f++]=I}for(;h<=_;){let I=n[h++];I!==null&&ht(I)}return this.ut=a,pt(t,u),$}});var oi="important",vs=" !"+oi,B=ae(class extends Z{constructor(t){if(super(t),t.type!==L.ATTRIBUTE||t.name!=="style"||t.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(t){return Object.keys(t).reduce((e,r)=>{let i=t[r];return i==null?e:e+`${r=r.includes("-")?r:r.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${i};`},"")}update(t,[e]){let{style:r}=t.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(e)),this.render(e);for(let i of this.ft)e[i]==null&&(this.ft.delete(i),i.includes("-")?r.removeProperty(i):r[i]=null);for(let i in e){let n=e[i];if(n!=null){this.ft.add(i);let o=typeof n=="string"&&n.endsWith(vs);i.includes("-")||o?r.setProperty(i,o?n.slice(0,-11):n,o?oi:""):r[i]=n}}return $}});var N=ae(class extends Z{constructor(t){if(super(t),t.type!==L.PROPERTY&&t.type!==L.ATTRIBUTE&&t.type!==L.BOOLEAN_ATTRIBUTE)throw Error("The `live` directive is not allowed on child or event bindings");if(!ii(t))throw Error("`live` bindings can only contain a single expression")}render(t){return t}update(t,[e]){if(e===$||e===c)return e;let r=t.element,i=t.name;if(t.type===L.PROPERTY){if(e===r[i])return $}else if(t.type===L.BOOLEAN_ATTRIBUTE){if(!!e===r.hasAttribute(i))return $}else if(t.type===L.ATTRIBUTE&&r.getAttribute(i)===e+"")return $;return pt(t),e}});var Zt="parcels";function re(t,e,r){return t.callService(Zt,e,r,void 0,!1)}async function ai(t,e,r){let n=(await t.callService(Zt,e,r,void 0,!1,!0))?.response;if(typeof n!="object"||n===null)return null;let o=n.parcel_id;return typeof o=="string"&&o!==""?o:null}function j(t,e,r={}){return t.callWS({...r,type:`${Zt}/${e}`})}var de={amazon:"Amazon Logistics",asendia:"Asendia",bpost:"bpost",brt:"BRT",cainiao:"Cainiao",chronopost:"Chronopost",colissimo:"Colissimo",correos:"Correos",correos_express:"Correos Express",ctt:"CTT",ctt_expresso:"CTT Expresso",deutsche_post:"Deutsche Post",dhl:"DHL",dpd:"DPD",evri:"Evri",fedex:"FedEx",gls:"GLS",hermes:"Hermes",inpost:"InPost",la_poste:"La Poste",mondial_relay:"Mondial Relay",mrw:"MRW",nacex:"Nacex",paack:"Paack",postnl:"PostNL",poste_italiane:"Poste Italiane",royal_mail:"Royal Mail",sda:"SDA",seur:"SEUR",tnt:"TNT",ups:"UPS",usps:"USPS",vinted_go:"Vinted Go",yunexpress:"YunExpress",other:"Other"};function mt(){return Object.entries(de).filter(([t])=>t!=="other").map(([t,e])=>({id:t,name:e})).sort((t,e)=>t.name.localeCompare(e.name,"en",{sensitivity:"base"})).concat([{id:"other",name:de.other??"Other"}])}function li(t){return Object.hasOwn(de,t)?de[t]??t:t}var s={weekCardName:"Parcels week",weekCardDescription:"A Monday to Sunday calendar of your parcel deliveries.",listCardName:"Parcels without a date",listCardDescription:"Active parcels that don't have a delivery date yet.",reviewCardName:"Parcels review",reviewCardDescription:"E-mails that need a decision before Parcels uses them. Only shown to administrators.",defaultWeekTitle:"Parcels",defaultListTitle:"No date yet",defaultReviewTitle:"Parcels review",loading:"Loading parcels\u2026",loadError:"Couldn't load parcels: {message}",refreshError:"Couldn't update parcels: {message}",unknownError:"Unknown error",close:"Close",cancel:"Cancel",save:"Save",dismissMessage:"Dismiss message",configInvalid:"Invalid configuration: expected a map of options.",configTitle:'Invalid configuration: "title" must be text.',configShowArchived:'Invalid configuration: "show_archived" must be true or false.',previousWeek:"Previous week",nextWeek:"Next week",today:"Today",goToToday:"Go to the current week",weekNavigation:"Week navigation",weekOf:"Week of {range}",refresh:"Check mailboxes now",refreshFailed:"Couldn't check the mailboxes: {message}",addParcel:"Add parcel",noDeliveriesThisWeek:"No deliveries this week",noDeliveriesThisDay:"No deliveries",filterLabel:"Show parcels",filterAll:"All",filterActive:"Active",filterRecent:"Recent",filterRecentHint:"Changed or expected this week",filterCompleted:"Completed",filterEmptyWeek:"Nothing to show this week with this filter",filterNote:"Filter: {filter}",filterShowAll:"Show all",todayTag:"Today",privateParcel:"Private parcel",unnamedParcel:"Parcel",packages:"{count} packages",carrierNotKnown:"Carrier not known yet",carrierNotKnownLabel:"carrier not known yet",carrierIs:"carrier {carrier}",hasCode:"PIN in the details",pin:"PIN {code}",unknownSeller:"Unknown seller",itemsCount:"{count} items",itemsNotKnown:"Items not known yet",possibly:"Possibly: {items}",possiblyOr:" or ",itemsMore:"{name} +{count}",possibleMatches:"Possibly the same package as",possibleHintOrderMany:"Not confirmed: the carrier's e-mails for these deliveries don't name an order. Merge the one this package came in, or rule out the others.",possibleHintOrderOne:"Not confirmed: the carrier's e-mails for this delivery don't name an order. Merge it if this package came in it, or rule it out.",possibleHintDeliveryMany:"Not confirmed: the carrier's e-mails for this delivery don't name an order. Merge the order that came in it, or rule out the others.",possibleHintDeliveryOne:"Not confirmed: the carrier's e-mails for this delivery don't name an order. Merge the order if it came in it, or rule it out.",possibleHintStemMany:"Not confirmed: this parcel's e-mails name only a shipment that several packages share. Merge the package they're about, or rule out the others.",possibleHintStemOne:"Not confirmed: this parcel's e-mails name only a shipment reference. Merge the package if they're about it, or rule it out.",possibleHintShipment:"Not confirmed: an e-mail names only the shipment this package is part of. Merge it if it's about this package, or rule it out.",candidateEmail:"1 e-mail from {name}",candidateEmails:"{count} e-mails from {name}",candidateUpdate:"1 update from {name}",candidateUpdates:"{count} updates from {name}",candidateMore:"+{count} more",carrierEmailsNoItems:"Carrier e-mails don't list items",trackingNoItems:"Tracking updates don't list items",couldAlsoBe:"Could also be: {list}",couldAlsoBeOrder:"{items} (order {tail})",notThisOne:"Not this one",notThisOneLabel:"{candidate} isn't {title}",aiBadge:"AI",aiBadgeLabel:"found by the local AI",aiFilledLabel:"details filled in by the local AI",privateLabel:"private",autoMerged:"Auto-merged \u2014 check",autoMergedLabel:"merged automatically, please check",undo:"Undo",undoMergeLabel:"Undo the automatic merge of {title}",undoFailed:"Couldn't undo the merge: {message}",keep:"Keep",keepMergeLabel:"Keep the automatic merge of {title}",keepFailed:"Couldn't keep the merge: {message}",inferred:"Delivery inferred \u2014 check",inferredLabel:"delivery inferred, please check",undoInferredLabel:"Undo the inferred delivery of {title}",undoInferredFailed:"Couldn't undo the delivery: {message}",keepInferredLabel:"Keep the inferred delivery of {title}",keepInferredFailed:"Couldn't keep the delivery: {message}",continuesBefore:"started before this week",continuesAfter:"continues after this week",deliveredOn:"delivered {date}",returnedOn:"returned {date}",expectedOn:"expected {date}",readyForPickupSince:"ready for pickup since {date}",statusOn:"{status} on {date}",windowFrom:"from {time}",windowUntil:"until {time}",noUndatedParcels:"Every active parcel has a delivery date.",noUndatedMatch:"No parcels without a date match this filter.",tabReview:"Needs review",tabFiltered:"Filtered",tabCount:"{label} ({count})",possibleDuplicate:"Possible duplicate",suggestionTitle:"Same parcel as {parcel}?",suggestionHint:"Merge the parcel that is the same one, or keep them apart.",reasonIs:"Reason: {reason}",mergeSuggested:"Merge",mergeSuggestedLabel:"Merge {candidate} into {title}",keepApart:"Keep apart",keepApartLabel:"Keep {title} apart from these parcels",reviewTabs:"Review lists",emptyReview:"Nothing to review.",emptyFiltered:"No filtered e-mails.",filteredHint:"E-mails the local AI classed as not about a parcel, and e-mails removed from a parcel in its details. Restore reads one again.",receivedOn:"Received {date}",noSubject:"(no subject)",mailboxOf:"Mailbox: {owner}",unverifiedSender:"Unverified sender",unverifiedSenderHint:"This e-mail didn't pass the sender checks (DKIM/DMARC). Make sure it's genuine before you accept it.",aiSuggestionLabel:"read by the local AI",suggestion:"Suggestion",noSuggestion:"No suggestion. Use Edit to enter the details yourself.",accept:"Accept",acceptWithChanges:"Accept with changes",edit:"Edit",dismiss:"Dismiss",trustSender:"Trust this sender",trustSenderHint:"Treat e-mails from {domain} as a known sender from now on",trustQuestion:"Trust {domain}? This e-mail failed the sender checks, and anyone can send e-mail that claims to come from {domain}. Its e-mails waiting here will be added as they are.",trustConfirm:"Trust {domain}",trustedSenderNote:"You trust {domain}, but this e-mail failed the sender checks. Make sure it's genuine before you accept it.",trustDone:"Trusted {domain}.",trustDoneWith:"Trusted {domain}: {parts}.",trustAddedOne:"added 1 e-mail",trustAddedMany:"added {count} e-mails",trustRecheckOne:"reading 1 e-mail again",trustRecheckMany:"reading {count} e-mails again",trustKeptOne:"1 still needs review",trustKeptMany:"{count} still need review",senderChecks:"Sender check details",failedChecks:"Checks the AI answer failed",aiNotes:"Notes on the AI answer",aiNotesHint:"What Parcels changed in the answer while checking it. These aren't failed checks.",checkHeaders:"Authentication headers",checkServers:"Servers, in order",checkNoServer:"(no name)",checkOriginals:"Renamed by the mail provider",checkUsed:"Header used",checkUsedNone:"None",checkUsedHeader:"Header {n}",checkNoResult:"none",ignoreSender:"Ignore this sender",ignoreSenderHint:"Skip e-mails from {domain} from now on",restore:"Restore",clear:"Clear",clearHint:"Remove this e-mail from the list. It won't be read again.",clearAll:"Clear all",clearAllQuestion:"Clear all filtered e-mails? They won't be read again.",aiQueueOne:"1 e-mail waiting for the local AI",aiQueueMany:"{count} e-mails waiting for the local AI",aiQueueMinutes:"{queue}, about {minutes} min",aiQueueHours:"{queue}, about {hours} h",fieldKind:"Type",fieldMerchant:"Merchant",fieldCarrier:"Carrier",fieldTrackingNumber:"Tracking number",fieldTrackingNumbers:"Tracking numbers",fieldOrderNumbers:"Order numbers",fieldReference:"Shipment reference",fieldEtaStart:"Expected from",fieldEtaEnd:"Expected until",fieldWindowStart:"Time window from",fieldWindowEnd:"Time window until",fieldPickupPoint:"Pickup point",fieldPickupCode:"PIN or pickup code",fieldItems:"Items",fieldPrivate:"Private (only the owners can see it)",hintList:"Separate with commas or new lines.",hintItems:"One per line.",carrierAuto:"Detect automatically",carrierUnknown:"Unknown",details:"Parcel details",status:"Status",sinceDate:"since {date}",dateNotKnown:"Date not known",dateNotKnownInline:"date not known",dayTimeNotKnown:"{day}, time not known",carrier:"Delivered by",notKnownYet:"Not known yet",trackOnline:"Track on the carrier's site",opensInNewTab:"(opens in a new tab)",trackingNumber:"Tracking number",copy:"Copy",copyTrackingNumber:"Copy the tracking number",copied:"Copied.",copyFailed:"Couldn't copy automatically. The number is selected, so you can copy it yourself.",merchant:"Merchant",seller:"Sold by",parcelAppName:"Name in the Parcel app",orders:"Orders",references:"Shipment reference",items:"Items",expected:"Expected",timeWindow:"Time window",pickupPoint:"Pickup point",pickupCode:"PIN or pickup code",packagesInShipment:"Packages",showPackage:"Show package {name}",showParcel:"Show parcel {name}",parcelId:"Parcel ID",delivered:"Delivered",timeline:"Timeline",noTimeline:"No events yet.",provisional:"Provisional",provisionalHint:"Made from an order e-mail. It's completed when the shipping e-mail arrives.",archived:"Archived",private:"Private",loadingDetails:"Loading details\u2026",detailsError:"Couldn't load the details: {message}",retry:"Try again",notFound:"This parcel no longer exists.",aiNotice:"Found by the local AI. Check the details, then confirm them.",aiFilledNotice:"Some details were filled in by the local AI. Check them, then confirm.",confirm:"Confirm",confirmLabel:"Confirm the details the local AI found",confirmFilledLabel:"Confirm the details the local AI filled in",mergedNotice:"Merged automatically ({reason}). Check that it's one parcel.",mergedNoticeNoReason:"Merged automatically. Check that it's one parcel.",inferredNotice:"Probably delivered: another parcel from this shop was delivered around the expected day. Undo if it hasn't arrived.",inferredQuietNotice:"Probably delivered: no news for three weeks. Undo if it hasn't arrived.",markDelivered:"Mark delivered",editDate:"Edit date",checkAgain:"Check again",checkingAgain:"Checking\u2026",checkAgainHint:"Read this parcel's e-mails again, and let the local AI look for what's missing",checkAgainReadOne:"Read 1 e-mail again.",checkAgainReadMany:"Read {count} e-mails again.",checkAgainGoneOne:"1 e-mail is no longer in the mailbox.",checkAgainGoneMany:"{count} e-mails are no longer in the mailbox.",checkAgainFailedOne:"1 e-mail couldn't be downloaded; try again later.",checkAgainFailedMany:"{count} e-mails couldn't be downloaded; try again later.",checkAgainNoEmails:"This parcel has no e-mails to read again.",checkAgainQueuedOne:"The local AI is checking 1 e-mail.",checkAgainQueuedMany:"The local AI is checking {count} e-mails.",checkAgainSuggest:"What it finds waits under Needs review.",checkAgainAuto:"What it finds is added to this parcel.",checkAgainNothingForAi:"There was nothing for the local AI to fill in.",checkAgainAiOff:"The local AI is off.",mergeWith:"Merge with\u2026",split:"Split\u2026",archive:"Archive",actions:"Actions",mergeIntro:"Choose the parcel to merge into this one. Likely matches come first.",mergeChoose:"Parcel",mergeConfirm:"Merge",mergeChooseFirst:"Choose a parcel first.",mergeSearch:"Search",mergeSearchPlaceholder:"Shop, item, order, number or carrier",mergeShowOlder:"Show older ({count})",mergeNoMatch:"No parcel matches the search.",noMergeCandidates:"There are no other parcels to merge with.",numberTail:"No. {tail}",orderTail:"Order {tail}",splitIntro:"Choose what to move to a new parcel.",splitConfirm:"Split off",splitHint:"Choose at least one, but not all of them.",archiveQuestion:"Archive this parcel? It no longer counts as active.",dateEndBeforeStart:"The end date is before the start date.",dateEndWithoutStart:"Set a start date too.",windowEndBeforeStart:"The time window must end after it starts.",actionFailed:"That didn't work: {message}",dayAtTime:"{day} at {time}",originsTitle:"E-mails ({count})",originsAndUpdatesTitle:"E-mails and updates ({count})",originsHint:"What each e-mail and source said and added to this parcel, oldest first.",originEmail:"E-mail",originEdits:"Changed by hand",factShop:"Shop: {name}",factSeller:"Sold by {name}",factShipment:"Shipment {n}/{total}",factCarrierNumber:"{carrier} No. {tail}",factReference:"Reference {tail}",factPickup:"Pickup: {place}",factName:"Name: {name}",originItems:"Items",originAiAll:"read by the local AI",originAiPart:"partly read by the local AI",originRepeats:"{count} more from {sender}",originRepeatsLatest:"latest: {said}",moveToNewParcel:"Move to a new parcel",moveToNewParcelLabel:"Move to a new parcel: {row}",removeFromParcels:"Remove from Parcels",removeFromParcelsLabel:"Remove from Parcels: {row}",splitBlockedNothingLeft:"Can't move: nothing else would be left in this parcel.",splitBlockedShared:"Can't move: it shares the tracking number or shipment with other e-mails here.",splitBlockedOther:"Can't move this one to a new parcel.",movedNotice:"Moved to a new parcel.",movedBackNotice:"Moved back into this parcel.",removedNotice:"Removed from Parcels. It's listed under Filtered in Needs review.",removedGoneNotice:"Removed from Parcels. Nothing else was left in this parcel, so it's gone. Undo reads the e-mail again.",restoredNotice:"Restored. The e-mail was read again.",restoredElsewhereNotice:"Restored. The e-mail was read again into another parcel.",restoredReviewNotice:"Restored. The e-mail is no longer in the mailbox, so it waits under Needs review.",restoredNoParcelNotice:"Restored. The e-mail was read again, but it isn't part of a parcel now. Look under Needs review.",showOtherParcel:"Show",showOtherParcelLabel:"Show that parcel",removedFromParcel:"Removed from a parcel",addTitle:"Add parcel",addSubmit:"Add",trackingRequired:"Enter a tracking number.",returnBadge:"Return",privateReturn:"Private return",returnTo:"Return to {merchant}",returnPlain:"Return",returnPickup:"Return pickup",returnPickedUp:"Return picked up",returnReceived:"Received by the shop",returnStarted:"Return started",pickupOn:"pickup {date}",pickedUpOn:"picked up {date}",returnStartedOn:"started {date}",receivedByShopLabel:"received by the shop",pickupRuleEmail:"date from the e-mail",pickupRuleNextWorkingDay:"the e-mail says the next working day",pickupRuleAssumed:"usually the working day after the e-mail",returnDetails:"Return details",pickup:"Pickup",returnStartedDay:"Started",returnCarrier:"Carrier",returnSentBackFrom:"Original delivery",returnEmails:"E-mails",returnNotFound:"This return no longer exists.",returnHint:"Items you send back to a shop. Their parcel keeps its delivery; the return shows on its pickup day.",removeReturn:"Remove",removeReturnQuestion:"Remove this return? Its e-mails won't be read again, and a delivery worked out only from it is undone.",inferredReturnNotice:"Probably delivered: you're sending its items back. Undo if it hasn't arrived."},di={ordered:"Ordered",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",exception:"Problem with delivery",ready_for_pickup:"Ready for pickup",returned:"Returned to sender",cancelled:"Cancelled"},ft={order:"Order confirmation",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",ready_for_pickup:"Ready for pickup",delayed:"Delayed",customs:"Held at customs",return:"Returned to sender",customer_return:"Return pickup",cancelled:"Cancelled",code:"Delivery code",not_parcel:"Not about a parcel",unknown:"Unknown"},ci={parser:"E-mail",ai:"Local AI",manual:"Added by hand",seventeentrack:"17TRACK",parcelapp:"Parcel app",inferred:"Inferred from another delivery",inferred_return:"Inferred from a return",quiet:"No news for three weeks"},ui={unknown_sender:"Unknown sender",not_aligned:"The sender's domain isn't authenticated (DKIM/DMARC)",no_auth_header:"No authentication results in the e-mail",untrusted_authserv:"Authentication results from an unknown server",multiple_auth_results:"More than one set of authentication results, so it can't tell which is real",low_confidence:"Not sure about the details",unknown_format:"Unknown e-mail format",ai_suggestion:"Read by the local AI",ai_fill:"The local AI found details the parser missed",ai_unavailable:"The local AI wasn't available",ai_timeout:"The local AI took too long on this e-mail",ai_rejected:"The local AI's answer didn't pass the checks",restored:"Moved back from Filtered"},pi={not_a_mapping:"The answer isn't a JSON object. Nothing in it is used.",kind_invalid:"The kind is missing, or isn't a kind Parcels knows. Nothing in the answer is used.",merchant_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',carrier_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',tracking_numbers_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',order_numbers_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',eta_start_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',eta_end_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',window_start_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',window_end_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',pickup_point_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',pickup_code_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',tracking_numbers_invalid:"The field is neither a list nor a text.",order_numbers_invalid:"The field is neither a list nor a text.",items_invalid:"The field is neither a list nor a text.",tracking_numbers_too_many:"More than 20 tracking numbers, 10 order numbers or 10 items. The rest are dropped.",order_numbers_too_many:"More than 20 tracking numbers, 10 order numbers or 10 items. The rest are dropped.",items_too_many:"More than 20 tracking numbers, 10 order numbers or 10 items. The rest are dropped.",tracking_invalid:"A tracking number isn't text, isn't 4 to 40 letters and digits (spaces, dashes and dots aside), or fails its carrier's format or check digit.",tracking_not_in_email:"A tracking number isn't in the e-mail, nor a miscopy of exactly one number in it.",tracking_is_order:"A tracking number equals an order number, or the e-mail labels it as an order number.",tracking_is_pickup_code:"The e-mail writes a tracking number only as a delivery or pickup code.",tracking_is_other_number:"The e-mail labels a tracking number as a phone, tax or bank number.",order_invalid:"An order number isn't text, has more than 60 characters, or doesn't have 3 to 40 letters and digits, at least one of them a digit.",order_not_in_email:"An order number isn't in the e-mail, nor a miscopy of exactly one number in it.",order_is_part:"An order number is only part of longer, hyphen- or slash-joined numbers, and not exactly one of them can be an order number.",order_is_tracking:"An order number equals a tracking number whose format identifies it.",order_is_pickup_code:"The e-mail writes an order number only as a delivery or pickup code.",pickup_code_invalid:"The pickup code isn't text, has more than 20 characters, or isn't 3 or more letters and digits, spaces and hyphens aside.",pickup_code_not_in_email:"The pickup code isn't in the e-mail.",pickup_code_is_number:"The pickup code equals a tracking or order number.",pickup_point_invalid:"The pickup point isn't plain text, or has more than 120 characters.",merchant_invalid:"The merchant isn't plain text, or has more than 60 characters.",item_invalid:"An item isn't plain text.",carrier_unknown:"The carrier isn't text, or isn't a carrier Parcels knows.",carrier_not_in_email:"The carrier didn't send the e-mail, and the e-mail neither names it nor has a number whose format identifies it as that carrier's.",eta_start_unparsed:"A date can't be read.",eta_end_unparsed:"A date can't be read.",eta_start_out_of_range:"A date isn't between 2 days before and 60 days after the day the e-mail arrived.",eta_end_out_of_range:"A date isn't between 2 days before and 60 days after the day the e-mail arrived.",eta_end_before_start:"The last delivery day is before the first.",eta_not_delivery_date:"The date overlaps no delivery date in the e-mail, and it had passed when the e-mail arrived or the e-mail gives it as another date: a deadline, or an order, shipping, offer or replaced date.",eta_not_in_text:"The e-mail has no date, weekday or span at all. A delivery today, in an out-for-delivery e-mail, is allowed.",window_start_unparsed:"A time can't be read.",window_end_unparsed:"A time can't be read.",window_end_before_start:"The time window doesn't end after it starts.",window_without_date:"A time window comes without a date.",not_parcel_has_tracking:"The answer says the e-mail isn't about a parcel, but gives a tracking number, or the e-mail has one whose format identifies it."},hi={tracking_added_by_detector:"Parcels' own detector added a tracking number that the e-mail writes.",pickup_code_from_text:"The e-mail's only delivery or pickup code was used, as the answer gave none that the e-mail writes.",item_recommended:"Products the e-mail lists only under Buy again or Recommended for you were dropped.",item_is_number:"An item that was the parcel's tracking or order number, code or reference was dropped.",kind_from_text:"The e-mail's words give a different status from the answer's, and theirs was used.",out_for_delivery_not_today:"Out for delivery, with a later delivery date and no such words in the e-mail, was read as in transit.",eta_dropped_for_kind:"A date was dropped, as no delivery is pending in e-mails of this kind.",eta_from_text:"The date by the e-mail's delivery words was used, as the answer gave another date or none.",order_moved_to_tracking:"An order number in a carrier's e-mail was the parcel's tracking number.",order_from_text:"An order number was taken as the e-mail writes it: the whole joined number, or a miscopy repaired.",tracking_from_text:"A miscopied tracking number was replaced by the e-mail's own.",merchant_is_carrier:"The shop given was this e-mail's carrier, so it was dropped.",carrier_unproven:"The shop, such as Amazon, was given as the carrier without proof that it delivers, so the carrier was left empty.",merchant_from_sender_name:"A shop given as a domain was named from the sender's name.",merchant_from_text:"A shop given as a domain was named from a line of the e-mail.",pickup_point_not_pickup:"An address the e-mail doesn't give as a pickup point was dropped.",pickup_point_generic:"A generic pickup point, such as a branch, was dropped."},mi={same_number:"same tracking number",same_merchant_eta:"same shop and delivery date",same_merchant_day:"same shop, delivered on the expected day",same_merchant_domain:"the shop's tracked shipment followed its order",same_order:"same order",same_reference:"same shipment reference"};function p(t,e){return t.replace(/\{(\w+)\}/g,(r,i)=>Object.hasOwn(e,i)?String(e[i]):r)}function q(t){if(typeof t=="string"&&t.trim())return t;if(t&&typeof t=="object"){let e=t.message;if(typeof e=="string"&&e.trim())return e;let r=t.code;if(typeof r=="string"&&r.trim())return r}return s.unknownError}var ys=["a[href]","button:not([disabled])","input:not([disabled]):not([type='hidden'])","select:not([disabled])","textarea:not([disabled])","[tabindex]:not([tabindex='-1'])"].join(",");function ws(t){return[...t.querySelectorAll(ys)].filter(e=>!e.closest("[hidden], [inert]")&&e.getClientRects().length>0)}function fi(t,e){if(t.key!=="Tab"||t.altKey||t.ctrlKey||t.metaKey)return;let r=ws(e),i=r[0],n=r[r.length-1];if(!i||!n){t.preventDefault(),e.focus();return}let a=e.getRootNode().activeElement,d=a instanceof HTMLElement&&e.contains(a)&&a!==e;t.shiftKey&&(!d||a===i)?(t.preventDefault(),n.focus()):!t.shiftKey&&(!d||a===n)&&(t.preventDefault(),i.focus())}var ks="parcels-error",gi="parcels-open-parcel",_i="parcels-open-return",ce=class extends Q{static properties={hass:{attribute:!1},_open:{state:!0},_busy:{state:!0},_error:{state:!0}};_returnFocus=null;_pressedBackdrop=!1;_hadFocus=!1;_session=0;constructor(){super(),this.hass=void 0,this._open=!1,this._busy=!1,this._error=null}render(){return l`<dialog
      aria-labelledby="dialog-title"
      @close=${this._onClose}
      @keydown=${this._onKeyDown}
      @pointerdown=${this._onPointerDown}
      @click=${this._onClick}
    >
      ${this._open?this.renderContent():c}
    </dialog>`}renderContent(){return c}canLightDismiss(){return!this._busy}dialogClosed(){}get isOpen(){return this._open}async showDialog(e){this._session+=1,this._returnFocus=e,this._open=!0,this._busy=!1,this._error=null,await this.updateComplete;let r=this._dialog();!r||!this._open||!this.isConnected||(r.open||r.showModal(),this.focusInDialog("[data-autofocus]"))}closeDialog(){let e=this._dialog();e?.open&&e.close(),this._finishClose(!0)}focusInDialog(e){this.renderRoot.querySelector(`dialog ${e}`)?.focus()}async focusAfterRender(e){await this.updateComplete,this._open&&this.focusInDialog(e)}async runAction(e,r){if(this._busy)return;let i=this._session;this._busy=!0,this._error=null;try{await e(),this._open&&this._session===i&&r?.()}catch(n){let o=p(s.actionFailed,{message:q(n)});this._open&&this._session===i?this._error=o:this.dispatchEvent(new CustomEvent(ks,{detail:o}))}finally{this._session===i&&(this._busy=!1)}}disconnectedCallback(){super.disconnectedCallback(),this._finishClose(!1)}willUpdate(e){this._hadFocus=this._open&&!!this.shadowRoot?.activeElement}updated(e){this._hadFocus&&this._open&&!this.shadowRoot?.activeElement&&this.focusInDialog("[data-autofocus]"),this._hadFocus=!1}_dialog(){return this.renderRoot.querySelector("dialog")}_finishClose(e){if(!this._open)return;let r=this._returnFocus;this._returnFocus=null,this._open=!1,this._busy=!1,this._error=null,this._pressedBackdrop=!1,this.dialogClosed(),e&&r?.()}_onClose(e){let r=e.currentTarget;e.target===r&&!r.open&&this._finishClose(!0)}_onKeyDown(e){fi(e,e.currentTarget)}_onPointerDown(e){this._pressedBackdrop=e.target===e.currentTarget}_onClick(e){let r=this._pressedBackdrop&&e.target===e.currentTarget;this._pressedBackdrop=!1,r&&this.canLightDismiss()&&this.closeDialog()}};var $s=/^(\d{4})-(\d{2})-(\d{2})$/,xs=/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)(?:[.,](\d+))?(Z|[+-]\d{2}(?::?\d{2})?)?$/i,Ss=[31,28,31,30,31,30,31,31,30,31,30,31];function Rs(t){return t%4===0&&t%100!==0||t%400===0}function Ts(t,e){return e===2&&Rs(t)?29:Ss[e-1]??0}function bt(t){if(typeof t!="string")return null;let e=$s.exec(t);if(!e)return null;let r=Number(e[1]),i=Number(e[2]),n=Number(e[3]);return i<1||i>12||n<1||n>Ts(r,i)?null:{year:r,month:i,day:n}}function D(t){return bt(t)!==null}function gt(t){let e=bt(t);if(!e)throw new RangeError(`Not a YYYY-MM-DD date: ${t}`);return e}function _t({year:t,month:e,day:r}){let i=e<=2?t-1:t,n=Math.floor(i/400),o=i-n*400,a=(e+9)%12,d=Math.floor((153*a+2)/5)+r-1,u=o*365+Math.floor(o/4)-Math.floor(o/100)+d;return n*146097+u-719468}function As(t){let e=t+719468,r=Math.floor(e/146097),i=e-r*146097,n=Math.floor((i-Math.floor(i/1460)+Math.floor(i/36524)-Math.floor(i/146096))/365),o=i-(365*n+Math.floor(n/4)-Math.floor(n/100)),a=Math.floor((5*o+2)/153),d=o-Math.floor((153*a+2)/5)+1,u=a<10?a+3:a-9;return{year:n+r*400+(u<=2?1:0),month:u,day:d}}function Cs({year:t,month:e,day:r}){return`${String(t).padStart(4,"0")}-${String(e).padStart(2,"0")}-${String(r).padStart(2,"0")}`}function ie(t,e){return Cs(As(_t(gt(t))+e))}function ue(t,e){return _t(gt(e))-_t(gt(t))}function Es(t){return((_t(gt(t))+3)%7+7)%7}function We(t){return ie(t,-Es(t))}function vi(t){return Array.from({length:7},(e,r)=>ie(t,r))}function k(t,e){return t<e?-1:t>e?1:0}function yi(t,e){return k(t,e)>=0?t:e}function A(t){if(typeof t!="string")return null;let e=xs.exec(t.trim());if(!e)return null;let[,r,i,n,o]=e;if(!r||!i||!D(r))return null;let a=n?`.${n.slice(0,3).padEnd(3,"0")}`:"",d="Z";if(o&&o.toUpperCase()!=="Z"){let m=o.slice(1).replace(":","").padEnd(4,"0");d=`${o[0]}${m.slice(0,2)}:${m.slice(2,4)}`}let u=Date.parse(`${r}T${i}${a}${d}`);return Number.isNaN(u)?null:u}var bi=new Map;function Ps(t){let e=bi.get(t);if(!e){let r={calendar:"gregory",numberingSystem:"latn",year:"numeric",month:"2-digit",day:"2-digit"};try{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:t})}catch{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:"UTC"})}bi.set(t,e)}return e}function C(t,e){if(D(t))return t;let r=A(t);if(r===null)return null;let i="",n="",o="";for(let d of Ps(e).formatToParts(r))d.type==="year"?i=d.value:d.type==="month"?n=d.value:d.type==="day"&&(o=d.value);let a=`${i.padStart(4,"0")}-${n}-${o}`;return D(a)?a:null}function Is(t){return[...new Set(t)]}function wi(t){return Is(t.split(/[\n,;]+/).map(e=>e.trim()).filter(Boolean))}function Ms(t){return t.split(/\r?\n/).map(e=>e.trim()).filter(Boolean)}function J(t){let e=/^(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?$/.exec((t??"").trim());if(!e)return null;let r=Number(e[1]),i=Number(e[2]);return r>23||i>59?null:`${String(r).padStart(2,"0")}:${String(i).padStart(2,"0")}`}function G(t){let e=t.trim();return e||null}function Os(t,e){return e&&!t?s.dateEndWithoutStart:t&&e&&k(e,t)<0?s.dateEndBeforeStart:null}function Ls(t,e){let r=J(t),i=J(e);return r&&i&&i<=r?s.windowEndBeforeStart:null}function ki(t){return{eta_start:t.eta_start??"",eta_end:t.eta_end??"",window_start:J(t.window_start)??"",window_end:J(t.window_end)??""}}function vt(t){let e=Os(t.eta_start,t.eta_end);if(e)return{message:e,field:e===s.dateEndWithoutStart?"eta_start":"eta_end"};let r=Ls(t.window_start,t.window_end);return r?{message:r,field:"window_end"}:null}function $i(t,e){return{parcel_id:t,eta_start:G(e.eta_start),eta_end:G(e.eta_end),window_start:J(e.window_start),window_end:J(e.window_end)}}var xi="shipped";function Jt(t){return{kind:t?.kind||xi,merchant:t?.merchant??"",carrier:t?.carrier??"",tracking_numbers:(t?.tracking_numbers??[]).join(", "),order_numbers:(t?.order_numbers??[]).join(", "),eta_start:t?.eta_start??"",eta_end:t?.eta_end??"",window_start:J(t?.window_start)??"",window_end:J(t?.window_end)??"",pickup_point:t?.pickup_point??"",pickup_code:t?.pickup_code??"",items:(t?.items??[]).join(`
`),reference:t?.reference??""}}function Si(t){return{kind:t.kind.trim()||xi,merchant:G(t.merchant),carrier:G(t.carrier),tracking_numbers:wi(t.tracking_numbers),order_numbers:wi(t.order_numbers),eta_start:G(t.eta_start),eta_end:G(t.eta_end),window_start:J(t.window_start),window_end:J(t.window_end),pickup_point:G(t.pickup_point),pickup_code:G(t.pickup_code),items:Ms(t.items),reference:G(t.reference)}}function Ri(t){let e=t.tracking_number.trim();if(!e)return null;let r={tracking_number:e},i=G(t.carrier);i&&(r.carrier=i);let n=G(t.merchant);return n&&(r.merchant=n),t.private&&(r.private=!0),r}function Xt(t,e){return t.length>0&&t.length<e}var Ns="https://github.com/fratei/ha-parcels";function z(t,e){customElements.get(t)||customElements.define(t,e)}function Ee(t,e,r){let i=window;Array.isArray(i.customCards)||(i.customCards=[]);let n=i.customCards;n.some(o=>o?.type===t)||n.push({type:t,name:e,description:r,preview:!0,documentationURL:Ns})}var K=S`
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
`,yt=S`
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
`,Pe=S`
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
`;var Ti={tracking_number:"",carrier:"",merchant:"",private:!1},er=class extends ce{static properties={_form:{state:!0},_missingNumber:{state:!0}};static styles=[K,Pe,S`
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
    `];constructor(){super(),this._form=Ti,this._missingNumber=!1}async open(e=null){this._form=Ti,this._missingNumber=!1,await this.showDialog(e)}canLightDismiss(){return!1}renderContent(){let e=this._form,r=this._missingNumber;return l`
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
              .value=${N(e.tracking_number)}
              aria-invalid=${r?"true":"false"}
              aria-describedby=${r?"tracking-error":c}
              @input=${this._onInput}
            />
          </label>
          ${r?l`<p class="field-error" id="tracking-error">${s.trackingRequired}</p>`:c}
          <label class="field">
            <span class="field-label">${s.fieldCarrier}</span>
            <select name="carrier" @change=${this._onInput}>
              <option value="" ?selected=${e.carrier===""}>${s.carrierAuto}</option>
              ${mt().map(i=>l`<option value=${i.id} ?selected=${e.carrier===i.id}>
                    ${i.name}
                  </option>`)}
            </select>
          </label>
          <label class="field">
            <span class="field-label">${s.fieldMerchant}</span>
            <input
              name="merchant"
              autocomplete="off"
              .value=${N(e.merchant)}
              @input=${this._onInput}
            />
          </label>
          <label class="check-row">
            <input
              type="checkbox"
              name="private"
              .checked=${N(e.private)}
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
          </div>`:c}
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
    `}_onInput(e){let r=e.currentTarget,i=r.name,n=r instanceof HTMLInputElement&&r.type==="checkbox"?r.checked:r.value;this._form={...this._form,[i]:n},i==="tracking_number"&&this._missingNumber&&r.value.trim()&&(this._missingNumber=!1)}_submit(e){e.preventDefault();let r=this.hass;if(!r||this._busy)return;let i=Ri(this._form);if(!i){this._missingNumber=!0,this.focusAfterRender("#tracking-number");return}this.runAction(()=>re(r,"add",i),()=>this.closeDialog())}};z("parcels-add-dialog",er);var ye=ae(class extends Z{constructor(t){if(super(t),t.type!==L.ATTRIBUTE||t.name!=="class"||t.strings?.length>2)throw Error("`classMap()` can only be used in the `class` attribute and must be the only part in the attribute.")}render(t){return" "+Object.keys(t).filter(e=>t[e]).join(" ")+" "}update(t,[e]){if(this.st===void 0){this.st=new Set,t.strings!==void 0&&(this.nt=new Set(t.strings.join(" ").split(/\s/).filter(i=>i!=="")));for(let i in e)e[i]&&!this.nt?.has(i)&&this.st.add(i);return this.render(e)}let r=t.element.classList;for(let i of this.st)i in e||(r.remove(i),this.st.delete(i));for(let i in e){let n=!!e[i];n===this.st.has(i)||this.nt?.has(i)||(n?(r.add(i),this.st.add(i)):(r.remove(i),this.st.delete(i)))}return $}});function Ds(t){try{return Intl.DateTimeFormat.supportedLocalesOf([t]),t}catch{return"en"}}function Fs(){let t=new Intl.DateTimeFormat(void 0,{hour:"numeric"}).resolvedOptions().hourCycle;return t==="h11"||t==="h12"}function Ie(t,e){let r=Ds(t?.locale?.language||t?.language||"en"),i=t?.locale?.time_format,n;i==="12"?n=!0:i==="24"?n=!1:i==="system"&&(n=Fs());let o=t?.locale?.time_zone==="local"?void 0:e||t?.config?.time_zone||void 0;return{language:r,hour12:n,timeZone:o}}var Ai=new Map;function ne(t,e,r){let i=e.hour!==void 0||e.timeStyle!==void 0,n={...e,timeZone:r?"UTC":t.timeZone};i&&t.hour12!==void 0&&(n.hour12=t.hour12);let o=JSON.stringify([t.language,n]),a=Ai.get(o);if(!a){try{a=new Intl.DateTimeFormat(t.language,n)}catch{a=new Intl.DateTimeFormat(t.language,{...n,timeZone:void 0})}Ai.set(o,a)}return a}function tr(t){let e=bt(t);return e?new Date(Date.UTC(e.year,e.month-1,e.day)):null}var kt={weekday:"short",day:"numeric",month:"short"},Ci={day:"numeric",month:"short",year:"numeric"},we={dateStyle:"medium"};function F(t,e,r=kt){let i=tr(t);return i?ne(e,r,!0).format(i):t}function M(t,e,r,i=kt){let n=tr(t),o=tr(e);return!n||!o?[t,e].filter(Boolean).join(" \u2013 "):t===e?ne(r,i,!0).format(n):ne(r,i,!0).formatRange(n,o)}function wt(t,e){let r=/^(\d{1,2}):(\d{2})/.exec(t);if(!r)return t;let i=new Date(Date.UTC(1970,0,1,Number(r[1]),Number(r[2])));return ne(e,{hour:"numeric",minute:"2-digit"},!0).format(i)}function se(t,e,r){return t&&e?`${wt(t,r)}\u2013${wt(e,r)}`:t?p(s.windowFrom,{time:wt(t,r)}):e?p(s.windowUntil,{time:wt(e,r)}):null}function H(t,e){if(!t)return"";let r=A(t);return r===null?t:ne(e,{dateStyle:"medium",timeStyle:"short"},!1).format(r)}var Hs={hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23"};function Us(t,e){return t%1e3!==0?!1:ne({language:"en-GB",hour12:void 0,timeZone:e},Hs,!1).formatToParts(t).every(i=>i.type==="literal"||i.value==="00")}function qe(t,e){let r=t?A(t):null;if(r===null)return"";let i=ne(e,kt,!1).format(r);return Us(r,e.timeZone)?i:p(s.dayAtTime,{day:i,time:ne(e,{timeStyle:"short"},!1).format(r)})}function V(t,e,r=kt){let i=t?A(t):null;return i===null?"":p(s.dayTimeNotKnown,{day:ne(e,r,!1).format(i)})}function pe(t){if(typeof t!="string")return null;let e=t.trim();return e||null}function Ei(t){let e=t.trim();if(!/^[a-z0-9]+(?:[_-][a-z0-9]+)*$/.test(e))return e;let r=e.replace(/[_-]+/g," ");return r.charAt(0).toUpperCase()+r.slice(1)}function Ge(t,e){let r=pe(e);return r?Object.hasOwn(t,r)?t[r]??r:Ei(r):""}function x(t){let e=pe(t.carrier_name);if(e)return e;let r=pe(t.carrier);return!r||r==="other"?null:Object.hasOwn(de,r)?li(r):Ei(r)}function O(t){return t.restricted?s.privateParcel:pe(t.merchant)??pe(t.name)??x(t)??pe(t.tracking_number)??s.unnamedParcel}function Pi(t){let e=pe(t.name);return e&&!t.restricted&&e!==O(t)?e:null}function Ii(t){return t.eta_source==="parcelapp"?ke(t.eta_source):null}function U(t){return Ge(di,t)}function Ve(t){return Ge(ft,t)}function ke(t){return Ge(ci,t)}function Mi(t){switch(t.inferred_reason){case"quiet":return s.inferredQuietNotice;case"return":return s.inferredReturnNotice;default:return s.inferredNotice}}function Oi(t){return Ge(ui,t)}function Li(t,e){let r=pe(e);return r&&Object.hasOwn(t,r)?t[r]??null:null}function Ni(t){return Li(hi,t)}function Di(t){return Li(pi,t)}function $t(t){return Ge(mi,t)}var xt="var(--secondary-text-color, #727272)",Fi="var(--info-color, #039be5)",Bs="var(--warning-color, #ffa600)",js="var(--success-color, #43a047)",Hi="var(--error-color, #db4437)",zs="var(--purple-color, #926bc7)",Ui={ordered:xt,shipped:Fi,in_transit:Fi,out_for_delivery:Bs,delivered:js,attempted:Hi,exception:Hi,ready_for_pickup:zs,returned:xt,cancelled:xt};function Ye(t){return Object.hasOwn(Ui,t)?Ui[t]:xt}var Ks=new Set(["delivered","returned","cancelled"]);function $e(t){return!Ks.has(t)}function E(t){let e=D(t.eta_start)?t.eta_start:null,r=D(t.eta_end)?t.eta_end:null,i=e??r;return i?{start:i,end:r&&k(r,i)>=0?r:i}:null}function he(t){return $e(t.status)}function St(t,e){let r=A(t.status_time),i=A(e.status_time);return r!==i?r===null?1:i===null?-1:i-r:t.id<e.id?-1:t.id>e.id?1:0}function Ki(t){return t.filter(e=>he(e)&&!e.archived&&E(e)===null).sort(St)}var Ws=7,qs=9999;function Bi(t){return t.replace(/[^0-9a-z]/gi,"").toUpperCase()}function ji(t){return t.merchant?.trim().toLowerCase()??""}function Wi(t,e){let r=t.delivered_undated&&!t.delivered_timeless;return t.status!=="delivered"||t.inferred||r?null:C(t.delivered_at,e)}function zi(t,e){let r=Wi(t,e);if(r)return{start:r,end:r};let i=E(t);if(i)return i;let n=C(t.delivered_at??t.status_time,e);return n?{start:n,end:n}:null}function qi(t,e,r){let i=(n,o)=>{let a=Wi(n,r),d=C(o.shipped_at??o.ordered_at,r);return a!==null&&d!==null&&k(a,d)<0};return i(t,e)||i(e,t)}function rr(t,e,r){let i=zi(t,r),n=zi(e,r);return!i||!n?qs:k(i.end,n.start)<0?ue(i.end,n.start):k(n.end,i.start)<0?ue(n.end,i.start):0}function ir(t,{timeZone:e}){let r=new Set(t.order_numbers.map(Bi).filter(Boolean)),i=ji(t),n=o=>o.order_numbers.some(a=>r.has(Bi(a)))?0:i&&ji(o)===i?1:2;return(o,a)=>n(o)-n(a)||+!he(o)-+!he(a)||rr(t,o,e)-rr(t,a,e)||St(o,a)}function Gs(t,{today:e,timeZone:r}){if(t.archived||t.status==="cancelled")return!0;if(he(t))return!1;let i=C(t.delivered_at??t.status_time,r);return i!==null&&ue(i,e)>Ws}function Gi(t,e,r){let i=[],n=[];for(let o of t){if(o.id===e.id||o.restricted)continue;(Gs(o,r)||qi(e,o,r.timeZone)?n:i).push(o)}return i.sort(ir(e,r)),n.sort(St),{likely:i,older:n}}function Vi(t,e){let r=e.toLowerCase().split(/\s+/).filter(Boolean);return r.length?t.filter(i=>{let n=[i.merchant,x(i),i.tracking_number,...i.order_numbers,...i.items].filter(Boolean).join(" ").toLowerCase();return r.every(o=>n.includes(o))}):[...t]}function Yi(t){let e=new Map;for(let r of t??[]){let i=e.get(r.parcel.id)??[];for(let n of r.candidates)i.some(o=>o.id===n.id)||i.push(n);e.set(r.parcel.id,i)}return e}function nr(t,e){let r=[],i=new Set,n=(o,a,d)=>{i.has(a.id)||(i.add(a.id),r.push({suggestionId:o.id,parcel:a,candidateId:d,reason:o.reason}))};for(let o of t??[])if(o.parcel.id===e)for(let a of o.candidates)n(o,a,a.id);else o.candidates.some(a=>a.id===e)&&n(o,o.parcel,e);return r}function Qi(t,e,{timeZone:r}){let i=n=>rr(t,n.parcel,r);return e.filter(n=>!qi(t,n.parcel,r)).sort((n,o)=>i(n)-i(o)||St(n.parcel,o.parcel))}function Zi(t,e,r){return nr(t,e).map(i=>i.parcel).filter(i=>i.id!==r&&!i.archived&&!i.restricted&&i.status!=="cancelled"&&i.status!=="returned"&&(i.items.length>0||i.order_numbers.length>0))}function Ji(t){let e=t.length>1,r=t.some(i=>i.candidateId===i.parcel.id);return t.length&&t.every(i=>i.reason==="same_reference")?r?s.possibleHintShipment:e?s.possibleHintStemMany:s.possibleHintStemOne:r?e?s.possibleHintDeliveryMany:s.possibleHintDeliveryOne:e?s.possibleHintOrderMany:s.possibleHintOrderOne}function en(t,e,r){return e?.kind==="delivered"||e?.kind==="returned"?null:se(t.window_start,t.window_end,r)}function tn(t){return!t.restricted&&x(t)===null}function rn(t){return t!==void 0&&t>1?p(s.packages,{count:String(t)}):null}function Qe(t){return t.restricted?s.privateParcel:Rt(t.merchant)??s.unknownSeller}function ar(t){if(t.restricted)return null;let e=Rt(t.pickup_code);return e?p(s.pin,{code:e}):null}function nn(t,e){let r=e.placement??null,i=[],n=x(t);if(n&&i.push(n),e.showStatus){let d=U(t.status);d&&i.push(d)}let o=rn(e.count);o&&i.push(o),e.showRange&&r&&r.from!==r.to&&i.push(M(r.from,r.to,e.locale));let a=en(t,r,e.locale);return a&&i.push(a),tn(t)&&i.push(s.carrierNotKnown),i.join(" \xB7 ")}var Vs=/^\d{1,3}\s*[x×]\s+/i,Ys=/\s*(?:[,;(|[]|\s[-–—]\s)/,Xi=8;function Rt(t){if(typeof t!="string")return null;let e=t.replace(/\s+/g," ").trim();return e||null}function sn(t){let e=t.replace(Vs,""),r=e.search(Ys);return(r>0?e.slice(0,r):e).trim()||t}function on(t){let e=sn(t).split(" ").slice(0,3);for(;e.length>1&&e.join(" ").length>24;)e.pop();return e.join(" ")}function Qs(t){let e=sn(t).split(" "),r=e[0]??t;return r.length<4&&e.length>1?`${r} ${e[1]}`:r}function me(t){if(t.restricted)return null;let e=(t.items??[]).map(Rt).filter(n=>n!==null);if(e.length===0)return null;if(e.length===1)return e[0]??null;let r=e.map(e.length===2?on:Qs),i=r.slice(0,Xi);return r.length>Xi&&i.push("\u2026"),`${p(s.itemsCount,{count:String(e.length)})} \xB7 ${i.join(", ")}`}function an(t){let e=(t.items??[]).map(Rt).filter(n=>n!==null),r=e[0];if(t.restricted||r===void 0)return null;let i=on(r);return e.length>1?p(s.itemsMore,{name:i,count:String(e.length-1)}):i}function ln(t){let e=t.length===1?t[0]:void 0;if(e!==void 0){let i=me(e);return i?p(s.possibly,{items:i}):null}let r=[...new Set(t.map(an).filter(i=>i!==null))];return r.length?p(s.possibly,{items:r.join(s.possiblyOr)}):null}function dn(t,e){let{locale:r}=e,i=e.placement??null,n=[Qe(t)],o=rn(e.count);o&&n.push(o);let a=x(t);a?n.push(p(s.carrierIs,{carrier:a})):tn(t)&&n.push(s.carrierNotKnownLabel);let d=U(t.status),u=i?F(i.from,r):"";switch(i?.kind){case"delivered":n.push(p(s.deliveredOn,{date:u}));break;case"returned":n.push(p(s.returnedOn,{date:u}));break;case"pickup":n.push(p(s.readyForPickupSince,{date:u}));break;case"status":n.push(p(s.statusOn,{status:d,date:u}));break;case"eta":d&&n.push(d),n.push(p(s.expectedOn,{date:M(i.from,i.to,r)}));break;default:d&&n.push(d);break}let m=en(t,i,r);m&&n.push(m);let g=me(t);if(g?n.push(g):e.possibly&&!t.restricted&&n.push(e.possibly),!t.restricted){t.ai?n.push(s.aiBadgeLabel):t.ai_filled&&n.push(s.aiFilledLabel),t.auto_merged&&n.push(s.autoMergedLabel),t.inferred&&n.push(s.inferredLabel);let h=ar(t);h?n.push(h):t.has_code&&n.push(s.hasCode)}return(t.private||t.restricted)&&n.push(s.privateLabel),e.continuesBefore&&n.push(s.continuesBefore),e.continuesAfter&&n.push(s.continuesAfter),n.join(", ")}function xe(t){let e=t?.trim();if(!e)return null;if(e.length<=6)return e;let r=e.replace(/[^0-9a-z_]/gi,""),i="",n=0;for(let o=r.length-1;o>=0&&n<5;o-=1){let a=r.charAt(o);i=a+i,a!=="_"&&(n+=1)}return`\u2026${i.replace(/^_+/,"")}`}var sr=3;function Zs(t){let e=t.restricted?[]:t.senders??[];if(!e.length)return null;let r=e.slice(0,sr).map(i=>{let n=i.source!=="email",o=i.count<=1,a=n?o?s.candidateUpdate:s.candidateUpdates:o?s.candidateEmail:s.candidateEmails;return p(a,{count:String(i.count),name:i.name})});return e.length>sr&&r.push(p(s.candidateMore,{count:String(e.length-sr)})),r.join(", ")}function Js(t){let e=t.restricted?[]:t.senders??[],r=i=>i.source!=="email";return e.length&&e.every(r)?s.trackingNoItems:e.some(i=>i.carrier)&&e.every(i=>i.carrier||r(i))?s.carrierEmailsNoItems:s.itemsNotKnown}function Xs(t,e){let r=t.delivered_at??t.status_time,i=t.delivered_at?t.delivered_undated:t.status_undated,n=t.delivered_at?t.delivered_timeless:t.status_timeless;if(i)return n&&V(r,e)||s.dateNotKnownInline;if(!t.inferred){let d=qe(r,e);if(d)return d}let o=e.timeZone??Intl.DateTimeFormat().resolvedOptions().timeZone,a=C(r,o);return a?M(a,a,e):null}function Me(t,e){let r=[U(t.status)];if(he(t)){let a=E(t);r.push(a?M(a.start,a.end,e):null,se(t.window_start,t.window_end,e))}else r.push(Xs(t,e));let i=[x(t)??s.carrierNotKnown],n=xe(t.tracking_number);n&&i.push(p(s.numberTail,{tail:n}));let o=xe(t.order_numbers[0]);return o&&i.push(p(s.orderTail,{tail:o})),{title:Qe(t),when:r.filter(Boolean).join(" \xB7 "),carrier:i.join(" \xB7 "),items:me(t),emails:Zs(t),noItems:Js(t)}}function Ze(t,e){let r=Me(t,e);return[r.title,r.items,r.carrier,r.when].filter(Boolean).join(" \xB7 ")}var or=3;function cn(t){let e=t.slice(0,or).map(r=>{let i=an(r)??Qe(r),n=xe(r.order_numbers[0]);return n?p(s.couldAlsoBeOrder,{items:i,tail:n}):i});return e.length?(t.length>or&&e.push(p(s.candidateMore,{count:String(t.length-or)})),p(s.couldAlsoBe,{list:e.join("; ")})):null}function lr(t,e){let r=[],i=new Map;for(let n of t){let o=e(n),a=o===null?void 0:i.get(o);if(a){a.push(n);continue}let d=[n];r.push(d),o!==null&&i.set(o,d)}return r}function dr(t,...e){return t.restricted||t.shipment_group===null?null:JSON.stringify([t.shipment_group,t.status,...e])}function Oe(t,e){return t.id<e.id?-1:t.id>e.id?1:0}function un(t){return lr(t,e=>dr(e)).map(e=>{let r=[...e].sort(Oe);return{parcel:e.reduce((i,n)=>Oe(n,i)<0?n:i),members:r}})}function eo(t){return t.reduce((e,r)=>r!==null&&(e===null||r<e)?r:e,null)}function to(t){return t.reduce((e,r)=>r!==null&&(e===null||r>e)?r:e,null)}function pn(t,e){return e.length<2?t:{...t,window_start:eo(e.map(r=>r.window_start)),window_end:to(e.map(r=>r.window_end)),ai:e.some(r=>r.ai),ai_filled:e.some(r=>r.ai_filled),private:e.some(r=>r.private),has_code:e.some(r=>r.has_code),pickup_code:ro(e),items:io(t,e),auto_merged:e.find(r=>r.auto_merged)?.auto_merged??null,inferred:e.some(r=>r.inferred)}}function ro(t){let e=new Set;for(let r of t){let i=r.pickup_code?.trim();i&&e.add(i)}return e.size>0?[...e].join(", "):null}function io(t,e){let r=[...t.items],i=new Set(r);for(let n of e)for(let o of n.items)i.has(o)||(i.add(o),r.push(o));return r}function hn(t,e){let r=e.shipment_group;if(r===null||e.restricted)return[];let i=t.filter(n=>n.shipment_group===r&&!n.restricted).sort((n,o)=>(n.tracking_number??"").localeCompare(o.tracking_number??"","en",{numeric:!0})||Oe(n,o));return i.length>1?i:[]}var mn="var(--pink-color, #e91e63)",Le="mdi:package-up",no={email:s.pickupRuleEmail,next_working_day:s.pickupRuleNextWorkingDay,assumed:s.pickupRuleAssumed};function fn(t){let e=t?.replace(/\s+/g," ").trim();return e||null}function Se(t,e){return t.received||k(t.day,e)<0}function Re(t){return t.restricted?s.privateReturn:fn(t.merchant)??s.unknownSeller}function cr(t){return t?no[t]:null}function gn(t){return t.restricted?null:x(t)}function Je(t,e){return t.received?s.returnReceived:t.pickup===null?s.returnStarted:Se(t,e)?s.returnPickedUp:s.returnPickup}function _n(t,e){let r=Je(t,e),i=gn(t);return i?`${r} \xB7 ${i}`:r}function bn(t,e,r){let i=t.restricted?null:fn(t.merchant),n=[t.restricted?s.privateReturn:i?p(s.returnTo,{merchant:i}):s.returnPlain],o=F(t.day,e);if(t.pickup===null)n.push(p(s.returnStartedOn,{date:o}));else if(Se(t,r))k(t.day,r)<=0&&n.push(p(s.pickedUpOn,{date:o}));else{n.push(p(s.pickupOn,{date:o}));let u=cr(t.pickup_rule);u&&n.push(u)}t.received&&n.push(s.receivedByShopLabel);let a=gn(t);a&&n.push(p(s.carrierIs,{carrier:a}));let d=me(t);return d&&n.push(d),(t.private||t.restricted)&&n.push(s.privateLabel),n.join(", ")}function vn(t,e){return t.filter(r=>r.parcel_ids.includes(e))}function pr(t){return`.chip[data-parcels~="${CSS.escape(t)}"] button.chip-main`}function yn(t,e,r,i){let n=e?"true":"false";return l`<div class="merge-note">
    <ha-icon icon=${t.icon} aria-hidden="true"></ha-icon>
    <span class="merge-label"
      >${t.label}${t.detail?l` <span class="merge-detail">${t.detail}</span>`:c}</span
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
  </div>`}function so(t,e,r){let i=r&&(t.tracking_number?.trim()??null)||null;return{title:i?`${e} ${i}`:e,detail:i}}function oo(t,e,r){let{title:i,detail:n}=e;return yn({icon:"mdi:call-merge",label:s.autoMerged,detail:n,undoLabel:p(s.undoMergeLabel,{title:i}),keepLabel:p(s.keepMergeLabel,{title:i})},r.busy,()=>r.onUndoMerge(t),()=>r.onKeepMerge(t))}function ao(t,e,r){let{title:i,detail:n}=e;return yn({icon:"mdi:package-variant-closed-check",label:s.inferred,detail:n,undoLabel:p(s.undoInferredLabel,{title:i}),keepLabel:p(s.keepInferredLabel,{title:i})},r.busy,()=>r.onUndoInferred(t),()=>r.onKeepInferred(t))}var ur="\xA0";function Tt(t,e){let{locale:r}=e,i=e.placement??null,n=e.members&&e.members.length>1?e.members:[t],o=n.length>1,a=pn(t,n),d=O(a),u=ar(a),m=me(a),g=m===null&&!a.restricted?e.possibly??null:null,h=dn(a,{locale:r,placement:i,count:n.length,continuesBefore:e.continuesBefore,continuesAfter:e.continuesAfter,possibly:g}),_=nn(a,{locale:r,placement:i,count:n.length,showStatus:e.showStatus,showRange:e.showRange}),f={chip:!0,"cont-before":e.continuesBefore===!0,"cont-after":e.continuesAfter===!0,returned:a.status==="returned"},v={...e.position,"--chip-color":Ye(a.status)},I=l`<span class="chip-row" aria-hidden=${a.restricted?"true":c}>
    ${e.continuesBefore?l`<span class="cont">‹</span>`:c}
    ${a.status==="delivered"?l`<span class="check">✓</span>`:c}
    <span class="chip-text">
      <span class=${ye({"chip-title":!0,unknown:!a.restricted&&!a.merchant?.trim()})}
        >${Qe(a)}</span
      >
      <span class="chip-line">
        <span class="chip-meta">${_||ur}</span>
        ${u?l`<span class="chip-pin">${u}</span>`:c}
      </span>
      <span
        class=${ye({"chip-items":!0,unknown:m===null&&g===null&&!a.restricted,possibly:g!==null})}
        >${m??g??(a.restricted?ur:s.itemsNotKnown)}</span
      >
    </span>
    ${(a.ai||a.ai_filled)&&!a.restricted?l`<span class="badge ai">${s.aiBadge}</span>`:c}
    ${a.has_code&&!u&&!a.restricted?l`<ha-icon class="lock" icon="mdi:dialpad" title=${s.hasCode}></ha-icon>`:c}
    ${a.private||a.restricted?l`<ha-icon class="lock" icon="mdi:lock"></ha-icon>`:c}
    ${e.continuesAfter?l`<span class="cont">›</span>`:c}
  </span>`;return a.restricted?l`<div class=${ye(f)} style=${B(v)}>
      <div class="chip-main" title=${h}>
        <span class="sr-only">${h}</span>
        ${I}
      </div>
    </div>`:l`<div
    class=${ye(f)}
    style=${B(v)}
    data-parcel-id=${a.id}
    data-parcels=${n.map(R=>R.id).join(" ")}
  >
    <button
      type="button"
      class="chip-main"
      aria-haspopup="dialog"
      aria-label=${h}
      title=${h}
      @click=${R=>e.onOpen(t,R.currentTarget)}
    >
      ${I}
    </button>
    ${n.map(R=>{let oe=so(R,d,o);return l`${R.auto_merged?oo(R,oe,e):c}${R.inferred?ao(R,oe,e):c}`})}
  </div>`}function hr(t){return`.chip[data-return-id="${CSS.escape(t)}"] button.chip-main`}function wn(t,e){let r=bn(t,e.locale,e.today),i=me(t),n={chip:!0,return:!0,done:Se(t,e.today)},o={...e.position,"--chip-color":mn},a=l`<span class="chip-row" aria-hidden=${t.restricted?"true":c}>
    <ha-icon class="ret-icon" icon=${Le}></ha-icon>
    <span class="chip-text">
      <span class="chip-title">${Re(t)}</span>
      <span class="chip-line">
        <span class="chip-meta">${_n(t,e.today)}</span>
      </span>
      <span class="chip-items">${i??ur}</span>
    </span>
    ${t.private||t.restricted?l`<ha-icon class="lock" icon="mdi:lock"></ha-icon>`:c}
  </span>`;return t.restricted?l`<div class=${ye(n)} style=${B(o)}>
      <div class="chip-main" title=${r}>
        <span class="sr-only">${r}</span>
        ${a}
      </div>
    </div>`:l`<div class=${ye(n)} style=${B(o)} data-return-id=${t.id}>
    <button
      type="button"
      class="chip-main"
      aria-haspopup="dialog"
      aria-label=${r}
      title=${r}
      @click=${d=>e.onOpen(t,d.currentTarget)}
    >
      ${a}
    </button>
  </div>`}function kn(t,e){return e&&!t.restricted&&!t.archived&&he(t)&&E(t)===null}function At(t){return typeof t=="number"&&Number.isInteger(t)&&t>0?t:0}function mr(t){let e=t!==null&&typeof t=="object"?t:{};return{read:At(e.read),queued:At(e.queued),gone:At(e.gone),failed:At(e.failed)}}function Ct(t,e,r){return t<=0?null:t===1?e:p(r,{count:t})}function $n(t,e){if(t.read+t.gone+t.failed===0)return s.checkAgainNoEmails;let r=[Ct(t.read,s.checkAgainReadOne,s.checkAgainReadMany),Ct(t.gone,s.checkAgainGoneOne,s.checkAgainGoneMany),Ct(t.failed,s.checkAgainFailedOne,s.checkAgainFailedMany)];return t.queued>0?r.push(Ct(t.queued,s.checkAgainQueuedOne,s.checkAgainQueuedMany),e.mode==="suggest"?s.checkAgainSuggest:s.checkAgainAuto):t.read>0&&r.push(e.enabled?s.checkAgainNothingForAi:s.checkAgainAiOff),r.filter(i=>i!==null).join(" ")}function T(t){return typeof t=="object"&&t!==null&&!Array.isArray(t)}function b(t){return typeof t=="string"?t:null}function w(t){return typeof t=="string"?t:""}function P(t){return Array.isArray(t)?t.filter(e=>typeof e=="string"):[]}function y(t){return typeof t=="string"&&t!==""?t:null}function Xe(t){return Number.isSafeInteger(t)&&t>0?t:0}function lo(t){return typeof t=="number"&&Number.isFinite(t)&&t>=0?t:null}function Y(t,e){if(!Array.isArray(t))return[];let r=[];for(let i of t){let n=e(i);n!==null&&r.push(n)}return r}function co(t){return t==="shop"||t==="return"||t==="quiet"?t:null}function et(t){return t==="ai"||t==="manual"||t==="seventeentrack"||t==="parcelapp"?t:"parser"}function uo(t){return typeof t=="string"&&t?et(t):null}function po(t){return!T(t)||!y(t.origin)?null:{origin:w(t.origin),at:w(t.at),reason:w(t.reason)}}function ho(t){if(!T(t))return null;let e=y(t.name);return e?{name:e,source:t.source==="seventeentrack"||t.source==="parcelapp"?t.source:"email",carrier:t.carrier===!0,count:Math.max(1,Xe(t.count))}:null}function Et(t){if(!T(t))return null;let e=y(t.id);return e?{id:e,merchant:b(t.merchant),seller:b(t.seller),name:b(t.name),carrier:b(t.carrier),carrier_name:b(t.carrier_name),tracking_number:b(t.tracking_number),tracking_url:b(t.tracking_url),status:w(t.status),status_time:b(t.status_time),status_undated:t.status_undated===!0,status_timeless:t.status_timeless===!0,eta_start:b(t.eta_start),eta_end:b(t.eta_end),window_start:b(t.window_start),window_end:b(t.window_end),eta_source:uo(t.eta_source),delivered_at:b(t.delivered_at),delivered_undated:t.delivered_undated===!0,delivered_timeless:t.delivered_timeless===!0,inferred:t.inferred===!0,inferred_reason:co(t.inferred_reason),pickup_point:b(t.pickup_point),pickup_code:b(t.pickup_code),has_code:t.has_code===!0,order_numbers:P(t.order_numbers),references:P(t.references),items:P(t.items),private:t.private===!0,owners:P(t.owners),source:et(t.source),ai:t.ai===!0,ai_filled:t.ai_filled===!0,auto_merged:po(t.auto_merged),provisional:t.provisional===!0,archived:t.archived===!0,origins:P(t.origins),shipment_group:y(t.shipment_group),restricted:t.restricted===!0,senders:Y(t.senders,ho),ordered_at:y(t.ordered_at),shipped_at:y(t.shipped_at)}:null}function mo(t){return T(t)?{kind:w(t.kind),merchant:b(t.merchant),carrier:b(t.carrier),tracking_numbers:P(t.tracking_numbers),order_numbers:P(t.order_numbers),eta_start:b(t.eta_start),eta_end:b(t.eta_end),window_start:b(t.window_start),window_end:b(t.window_end),pickup_point:b(t.pickup_point),pickup_code:b(t.pickup_code),items:P(t.items),reference:b(t.reference)}:null}function fo(t){if(!T(t))return null;let e=y(t.id);return e?{id:e,created:w(t.created),received:b(t.received),sender:w(t.sender),sender_domain:w(t.sender_domain),subject:w(t.subject),mailbox_owner:b(t.mailbox_owner),reason:w(t.reason),authenticated:t.authenticated===!0,trusted_sender:t.trusted_sender===!0,checks:_o(t.checks),fill:t.fill===!0,errors:xn(t.errors),notes:xn(t.notes),source:t.source==="ai"?"ai":"parser",suggestion:mo(t.suggestion)}:null}var go=/^[a-z0-9_]{1,40}$/;function xn(t){if(!Array.isArray(t))return[];let e=t.filter(r=>typeof r=="string"&&go.test(r));return[...new Set(e)]}function _o(t){if(!T(t))return null;let e=Xe(t.headers),r=t.used;return{headers:e,servers:Array.isArray(t.servers)?t.servers.map(i=>typeof i=="string"?i:""):[],used:Number.isSafeInteger(r)&&r>=0&&r<e?r:null,dkim:w(t.dkim),dmarc:w(t.dmarc),spf:w(t.spf),originals:Xe(t.originals)}}function bo(t){if(!T(t))return null;let e=y(t.id);return e?{id:e,created:w(t.created),received:b(t.received),sender:w(t.sender),sender_domain:w(t.sender_domain),subject:w(t.subject),removed:t.removed===!0}:null}function vo(t){if(!T(t))return null;let e=y(t.id),r=Et(t.parcel),i=Y(t.candidates,Et);return!e||!r||!i.length?null:{id:e,reason:w(t.reason),merchant:b(t.merchant),day:D(t.day)?t.day:null,parcel:r,candidates:i}}function yo(t){return t==="suggest"||t==="auto"?t:"off"}function wo(t,e=Date.now()){let r=T(t)?t:{},i=y(r.time_zone)??"UTC",n=D(r.today)?r.today:C(new Date(e).toISOString(),i)??"1970-01-01";return{user_is_admin:r.user_is_admin===!0,ai_enabled:r.ai_enabled===!0,ai_mode:yo(r.ai_mode),ai_queue:Xe(r.ai_queue),ai_queue_seconds:lo(r.ai_queue_seconds),dashboard_url:w(r.dashboard_url),seventeentrack:r.seventeentrack===!0,time_zone:i,today:n}}function Sn(t,e=Date.now()){let r=T(t)?t:{};return{parcels:Y(r.parcels,Et),returns:Y(r.returns,xo),review:Y(r.review,fo),merge_suggestions:Y(r.merge_suggestions,vo),filtered:Y(r.filtered,bo),settings:wo(r.settings,e)}}function ko(t){return t==="email"||t==="next_working_day"||t==="assumed"?t:null}function $o(t){return T(t)?{time:b(t.time),label:w(t.label),source:et(t.source)}:null}function xo(t){if(!T(t))return null;let e=y(t.id);return!e||!D(t.day)?null:{id:e,merchant:b(t.merchant),carrier:b(t.carrier),carrier_name:b(t.carrier_name),tracking_number:b(t.tracking_number),tracking_url:b(t.tracking_url),day:t.day,pickup:D(t.pickup)?t.pickup:null,pickup_rule:ko(t.pickup_rule),started:b(t.started),received:t.received===!0,order_numbers:P(t.order_numbers),items:P(t.items),parcel_ids:P(t.parcel_ids),emails:Y(t.emails,$o),private:t.private===!0,owners:P(t.owners),archived:t.archived===!0,restricted:t.restricted===!0}}function So(t){return t==="inferred"||t==="inferred_return"||t==="quiet"?t:et(t)}function Ro(t){return T(t)?{time:w(t.time),status:w(t.status),source:So(t.source),label:w(t.label),undated:t.undated===!0,timeless:t.timeless===!0}:null}function To(t){return T(t)?{id:w(t.id),merchant:b(t.merchant),number:w(t.number),placed_at:b(t.placed_at),parcel_ids:P(t.parcel_ids)}:null}function Ao(t){if(!Array.isArray(t)||t.length!==2)return null;let[e,r]=t.map(Xe);return e&&r&&e<=r?[e,r]:null}function Co(t){if(!T(t))return null;let e=y(t.id);return e?{id:e,label:w(t.label),source:et(t.source),sender_name:y(t.sender_name),name:y(t.name),time:b(t.time),status:y(t.status),kind:y(t.kind),event_time:y(t.event_time),undated:t.undated===!0,timeless:t.timeless===!0,dayless:t.dayless===!0,eta_start:D(t.eta_start)?t.eta_start:null,eta_end:D(t.eta_end)?t.eta_end:null,window_start:y(t.window_start),window_end:y(t.window_end),carrier:y(t.carrier),carrier_name:y(t.carrier_name),tracking_number:y(t.tracking_number),reference:y(t.reference),merchant:y(t.merchant),seller:y(t.seller),order_numbers:P(t.order_numbers),items:P(t.items),pickup_point:y(t.pickup_point),shipment:Ao(t.shipment),email:t.email===!0,edits:t.edits===!0,part_of:y(t.part_of),split_blocked:y(t.split_blocked)}:null}function Rn(t){if(!T(t))return null;let e=Et(t.parcel);return e?{parcel:e,timeline:Y(t.timeline,Ro),orders:Y(t.orders,To),origins:Y(t.origins,Co)}:null}var Eo=6e4;function Te(t){let e=t?.trim();return e||null}function Po(t,e){let r=[t,...e],i=r.find(u=>u.status||u.kind)??t,n=r.find(u=>u.eta_start||u.window_start||u.window_end)??t,o=r.find(u=>u.carrier||u.carrier_name)??t,a=u=>r.find(m=>m[u]!==null&&m[u]!=="")?.[u]??t[u],d=u=>[...new Set(r.flatMap(m=>m[u]))];return{...t,status:i.status,kind:i.kind,event_time:i.event_time,undated:i.undated,timeless:i.timeless,dayless:i.dayless,eta_start:n.eta_start,eta_end:n.eta_end,window_start:n.window_start,window_end:n.window_end,carrier:o.carrier,carrier_name:o.carrier_name,tracking_number:a("tracking_number"),reference:a("reference"),merchant:a("merchant"),seller:a("seller"),pickup_point:a("pickup_point"),shipment:a("shipment"),name:a("name"),order_numbers:d("order_numbers"),items:d("items")}}function Io(t){return t.edits?s.originEdits:t.email?Te(t.sender_name)??Te(t.label)??s.originEmail:Te(t.label)??ke(t.source)}function Mo(t,e){let r=[],n=(t.kind&&t.kind!=="unknown"&&t.kind!=="not_parcel"?Ve(t.kind):"")||(t.status?U(t.status):"");if(n){r.push(n);let a=t.event_time?A(t.event_time):null,d=t.time?A(t.time):null;t.undated?r.push(t.timeless&&V(t.event_time,e)||s.dateNotKnownInline):a!==null&&(d===null||Math.abs(a-d)>=Eo)&&r.push(qe(t.event_time,e))}if(t.eta_start){let a=M(t.eta_start,t.eta_end??t.eta_start,e);r.push(p(s.expectedOn,{date:a}))}let o=se(t.window_start,t.window_end,e);return o&&r.push(o),r.join(" \xB7 ")}function Oo(t){let e=[],r=Te(t.merchant);r&&e.push(p(s.factShop,{name:r}));let i=Te(t.seller);i&&e.push(p(s.factSeller,{name:i}));for(let m of t.order_numbers){let g=xe(m);g&&e.push(p(s.orderTail,{tail:g}))}if(t.shipment){let[m,g]=t.shipment;e.push(p(s.factShipment,{n:String(m),total:String(g)}))}let n=x(t),o=xe(t.tracking_number);n&&o?e.push(p(s.factCarrierNumber,{carrier:n,tail:o})):n?e.push(n):o&&e.push(p(s.numberTail,{tail:o}));let a=xe(t.reference);a&&e.push(p(s.factReference,{tail:a}));let d=Te(t.pickup_point);d&&e.push(p(s.factPickup,{place:d}));let u=Te(t.name);return u&&e.push(p(s.factName,{name:u})),e}function Tn(t,e){let r=new Set(t.map(o=>o.id)),i=new Map;for(let o of t)o.part_of&&o.part_of!==o.id&&r.has(o.part_of)&&i.set(o.part_of,[...i.get(o.part_of)??[],o]);let n=[];for(let o of t){if(o.part_of&&o.part_of!==o.id&&r.has(o.part_of))continue;let a=i.get(o.id)??[],d=Po(o,a),u=Io(d),m=null;o.source==="ai"?m="all":a.length&&(m="part"),n.push({ids:[o.id,...a.map(g=>g.id)],lead:o.id,header:u,when:qe(o.time,e),said:Mo(d,e),facts:Oo(d),items:d.items.filter(g=>g.trim()),ai:m,email:o.email,edits:o.edits,splitBlocked:o.split_blocked,sender:`${o.email?"email":o.source}:${u}`})}return n}function An(t){let e=new Map,r=new Map;for(let o of t){if(!o.email||o.edits)continue;let a=e.get(o.sender),d=[...o.facts,...o.items.map(u=>`\0${u}`)];a&&d.every(u=>a.has(u))&&r.set(o.sender,[...r.get(o.sender)??[],o]),e.set(o.sender,new Set([...a??[],...d]))}let i=new Map;for(let o of r.values())if(o.length>=2)for(let a of o)i.set(a.lead,o);let n=[];for(let o of t){let a=i.get(o.lead);if(!a){n.push({type:"row",row:o});continue}let d=a[a.length-1];d.lead===o.lead&&n.push({type:"repeats",key:d.lead,header:o.header,rows:a,latest:d})}return n}function Cn(t){let e=t.every(r=>r.email)?s.originsTitle:s.originsAndUpdatesTitle;return p(e,{count:String(t.length)})}function En(t,e){let r=new Set(e);return t.filter(i=>r.has(i.lead)).flatMap(i=>i.ids)}function Pn(t){switch(t){case null:return null;case"nothing_left":return s.splitBlockedNothingLeft;case"shared_number":return s.splitBlockedShared;default:return s.splitBlockedOther}}function In(t,e,r){let i=t.parcels[0];return t.review!==null?{notice:"review",follow:null,show:null}:t.parcels.includes(e)?{notice:"restored",follow:null,show:null}:i===void 0?{notice:"noParcel",follow:null,show:null}:r?{notice:"restored",follow:i,show:null}:{notice:"elsewhere",follow:null,show:i}}function Pt(t){if(typeof t!="string")return null;let e=t.trim();if(!e)return null;let r;try{r=new URL(e)}catch{return null}return r.protocol!=="https:"||!r.hostname||r.username||r.password?null:r.href}var Mn={parcel:/^p_[0-9a-f]{1,64}$/,return:/^ret_[0-9a-f]{1,64}$/};function On(t){return Object.hasOwn(Mn,t)}function Ln(t){try{return decodeURIComponent(t.replaceAll("+"," "))}catch{return t}}function Nn(t){return t.replace(/^\?/,"").split("&").filter(e=>e!=="")}function Dn(t){let e=t.indexOf("=");return Ln(e<0?t:t.slice(0,e))}function Fn(t){for(let e of Nn(t)){let r=Dn(e);if(!On(r))continue;let i=e.indexOf("="),n=i<0?"":Ln(e.slice(i+1));if(Mn[r].test(n))return{kind:r,id:n}}return null}function Hn(t){let e=Nn(t),r=e.filter(i=>!On(Dn(i)));return r.length===e.length?t:r.length?`?${r.join("&")}`:""}var Lo={restored:s.restoredNotice,elsewhere:s.restoredElsewhereNotice,review:s.restoredReviewNotice,noParcel:s.restoredNoParcelNotice},No={weekday:"short",day:"numeric",month:"short",year:"numeric"},Un={eta_start:"",eta_end:"",window_start:"",window_end:""},Do=6;function Fo(t){return t.map((e,r)=>({entry:e,index:r,time:A(e.time)??-1/0})).sort((e,r)=>r.time-e.time||r.index-e.index).map(({entry:e})=>e)}var fr=class extends ce{static properties={snapshot:{attribute:!1},locale:{attribute:!1},_parcelId:{state:!0},_details:{state:!0},_loading:{state:!0},_loadError:{state:!0},_mode:{state:!0},_copyState:{state:!0},_dateForm:{state:!0},_formError:{state:!0},_mergeTarget:{state:!0},_mergeQuery:{state:!0},_mergeOlder:{state:!0},_mergeHint:{state:!0},_splitSelection:{state:!0},_pendingPrivate:{state:!0},_checking:{state:!0},_checkStatus:{state:!0},_originsOpen:{state:!0},_openFolds:{state:!0},_originNotice:{state:!0}};static styles=[K,Pe,S`
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
    `];_request=0;_checkRun=0;_loadedKey="";_rowsCache=null;constructor(){super(),this.snapshot=null,this.locale=Ie(void 0),this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._copyState="idle",this._dateForm=Un,this._formError=null,this._mergeTarget="",this._mergeQuery="",this._mergeOlder=!1,this._mergeHint=!1,this._splitSelection=[],this._pendingPrivate=null,this._checking=!1,this._checkStatus=null,this._originsOpen=!1,this._openFolds=new Set,this._originNotice=null}async open(e,r=null){this._parcelId=e,this._details=null,this._loadError=null,this._mode="view",this._copyState="idle",this._formError=null,this._pendingPrivate=null,this._checkRun+=1,this._checking=!1,this._checkStatus=null,this._resetOrigins(),this._load(),await this.showDialog(r)}_switchTo(e){this._busy||e===this._parcelId||(this._parcelId=e,this._details=null,this._loadError=null,this._error=null,this._mode="view",this._copyState="idle",this._formError=null,this._pendingPrivate=null,this._checkStatus=null,this._resetOrigins(),this._load(),this.focusAfterRender("[data-current-package]"))}_resetOrigins(){this._originsOpen=!1,this._openFolds=new Set,this._originNotice=null}dialogClosed(){this._request+=1,this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._pendingPrivate=null,this._checkRun+=1,this._checking=!1,this._checkStatus=null,this._resetOrigins()}canLightDismiss(){return this._mode==="view"&&!this._busy}willUpdate(e){if(super.willUpdate(e),!e.has("snapshot")||!this.isOpen||!this.snapshot)return;this._pendingPrivate=null;let r=this.snapshot.parcels.find(i=>i.id===this._parcelId);r&&JSON.stringify(r)!==this._loadedKey&&this._load()}get _parcel(){let e=this._parcelId;return e===null?null:this.snapshot?this.snapshot.parcels.find(r=>r.id===e)??null:this._details?.parcel??null}async _load(){let e=this.hass,r=this._parcelId;if(!e||r===null)return;let i=++this._request,n=this.snapshot?.parcels.find(o=>o.id===r);this._loadedKey=n?JSON.stringify(n):"",this._loading=!0,this._loadError=null;try{let o=await j(e,"get",{parcel_id:r});if(i!==this._request)return;let a=Rn(o);if(!a)throw new Error(s.unknownError);this._details=a}catch(o){i===this._request&&(this._loadError=q(o))}finally{i===this._request&&(this._loading=!1)}}renderContent(){let e=this._parcel;return l`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">
            ${e?O(e):s.details}
          </h2>
          ${e?this._renderBadges(e):c}
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
          </div>`:c}
      ${this._mode==="view"?this._renderStatus():c}
      ${e&&!e.restricted?this._renderActions(e):c}
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
                </button>`:c}
            ${e.undo?l`<button type="button" class="btn" aria-disabled=${r} @click=${e.undo}>
                  ${s.undo}
                </button>`:c}
            <button
              type="button"
              class="icon-btn"
              aria-label=${s.dismissMessage}
              title=${s.dismissMessage}
              @click=${this._dismissOriginNotice}
            >
              <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
            </button>
          </div>`:c}
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
          </div>`:c}
    </div>`}_renderBadges(e){let r=e.ai?s.aiBadgeLabel:s.aiFilledLabel;return l`<div class="dialog-badges">
      <span class="badge" style=${B({"--badge-color":Ye(e.status)})}>
        ${U(e.status)}
      </span>
      ${(e.ai||e.ai_filled)&&!e.restricted?l`<span class="badge ai" title=${r}>
            ${s.aiBadge}<span class="sr-only">, ${r}</span>
          </span>`:c}
      ${e.private||e.restricted?l`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${s.private}
          </span>`:c}
      ${e.provisional?l`<span class="badge info">${s.provisional}</span>`:c}
      ${this._returnsOf(e).length?l`<span class="badge return">
            <ha-icon icon=${Le} aria-hidden="true"></ha-icon>${s.returnBadge}
          </span>`:c}
      ${e.archived?l`<span class="badge">${s.archived}</span>`:c}
    </div>`}_returnsOf(e){return e.restricted?[]:vn(this.snapshot?.returns??[],e.id)}_renderBody(e){if(!e)return this.snapshot||!this._loading&&!this._loadError?l`<p class="empty">${s.notFound}</p>`:this._renderLoadState();switch(this._mode){case"date":return this._renderDateForm();case"merge":return this._renderMerge(e);case"split":return this._renderSplit();case"archive":return l`<p>${s.archiveQuestion}</p>`;default:return this._renderView(e)}}_renderLoadState(){return this._loadError?l`<div class="alert error" role="alert">
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
          </div>`:c}
      ${!r&&e.auto_merged?this._renderMergeNotice(e):c}
      ${!r&&e.inferred?this._renderInferredNotice(e):c}
      ${!r&&e.provisional?l`<p class="hint">${s.provisionalHint}</p>`:c}
      ${r?c:this._renderPossible(e)}
      ${this._renderFacts(e)}
      ${r?c:l`<label class="check-row switch-row">
            <input
              type="checkbox"
              role="switch"
              .checked=${N(this._pendingPrivate??e.private)}
              aria-disabled=${this._busy?"true":"false"}
              @click=${this._onPrivateClick}
              @change=${this._togglePrivate}
            />
            <span>${s.fieldPrivate}</span>
          </label>`}
      ${r?c:this._renderOrigins()}
      <h3 class="section-title">${s.timeline}</h3>
      ${this._details?this._renderTimeline(this._details.timeline):this._renderLoadState()}
    `}get _rows(){let e=this._details;if(!e)return[];let r=this._rowsCache;if(r?.details===e&&r.locale===this.locale)return r.rows;let i=Tn(e.origins,this.locale);return this._rowsCache={details:e,locale:this.locale,rows:i},i}get _splitRows(){return this._rows.filter(e=>!e.edits)}get _splitChosen(){let e=new Set(this._splitRows.map(r=>r.lead));return this._splitSelection.filter(r=>e.has(r))}_renderOrigins(){let e=this._rows;if(!e.length)return c;let r=this._splitRows.length>=2;return l`<details class="origins" .open=${this._originsOpen} @toggle=${this._onOriginsToggle}>
      <summary class="section-title" data-origins-summary>${Cn(e)}</summary>
      <p class="hint">${s.originsHint}</p>
      <ol class="origin-list">
        ${An(e).map(i=>this._renderOriginEntry(i,r))}
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
        ${n?l`<span class="muted">· ${p(s.originRepeatsLatest,{said:n})}</span>`:c}
      </span>
      ${i?l`<ol class="origin-list">
            ${e.rows.map(o=>l`<li class="origin" data-origin=${o.lead}>
                ${this._renderOriginBody(o,!1)}${this._renderRowActions(o,r)}
              </li>`)}
          </ol>`:c}
    </li>`}_renderOriginBody(e,r){let i=c;e.items.length&&r?i=l`<span class="origin-line origin-items">
        ${e.items.map(o=>l`<span class="origin-item">${o}</span>`)}
      </span>`:e.items.length&&(i=l`<ul class="origin-items" aria-label=${s.originItems}>
        ${e.items.map(o=>l`<li>${o}</li>`)}
      </ul>`);let n=e.ai==="all"?s.originAiAll:s.originAiPart;return l`<span class="origin-line">
        <strong>${e.header}</strong>${e.when?l`<span class="muted"> · ${e.when}</span>`:c}${e.ai?l`<span class="muted"> · ${n}</span>`:c}
      </span>
      ${e.said?l`<span class="origin-line">${e.said}</span>`:c}
      ${e.facts.length?l`<span class="origin-line muted">${e.facts.join(" \xB7 ")}</span>`:c}
      ${i}`}_renderRowActions(e,r){let i=e.email&&this.snapshot?.settings.user_is_admin===!0;if(e.edits||!r&&!i)return c;let n=r?Pn(e.splitBlocked):null,o=this._busy?"true":"false",a=e.when?`${e.header} \xB7 ${e.when}`:e.header,d=c;return n?d=l`<span class="hint">${n}</span>`:r&&(d=l`<button
        type="button"
        class="btn"
        data-move
        aria-label=${p(s.moveToNewParcelLabel,{row:a})}
        aria-disabled=${o}
        @click=${()=>this._moveRow(e)}
      >
        ${s.moveToNewParcel}
      </button>`),l`<span class="row-actions">
      ${d}
      ${i?l`<button
            type="button"
            class="btn"
            data-remove
            aria-label=${p(s.removeFromParcelsLabel,{row:a})}
            aria-disabled=${o}
            @click=${()=>this._removeRow(e)}
          >
            ${s.removeFromParcels}
          </button>`:c}
    </span>`}_renderPossible(e){let r=this.snapshot?.merge_suggestions,i=Qi(e,nr(r,e.id),this._dayContext());if(!i.length)return c;let n=this.locale,o=this._busy?"true":"false",a=O(e);return l`<section class="possible" aria-labelledby="possible-title">
      <h3 class="section-title" id="possible-title">${s.possibleMatches}</h3>
      <p class="hint">${Ji(i)}</p>
      <ul class="possible-list">
        ${i.map(d=>{let u=Ze(d.parcel,n);return l`<li class="possible-item" data-possible=${d.parcel.id}>
            ${this._renderCandidateLines(d.parcel,e.id)}
            <span class="possible-actions">
              <button
                type="button"
                class="btn"
                data-accept
                aria-label=${p(s.mergeSuggestedLabel,{candidate:u,title:a})}
                aria-disabled=${o}
                @click=${()=>this._acceptPossible(d)}
              >
                ${s.mergeSuggested}
              </button>
              <button
                type="button"
                class="btn"
                data-dismiss
                aria-label=${p(s.notThisOneLabel,{candidate:u,title:a})}
                aria-disabled=${o}
                @click=${()=>this._dismissPossible(d)}
              >
                ${s.notThisOne}
              </button>
            </span>
          </li>`})}
      </ul>
    </section>`}_renderMergeNotice(e){let r=$t(e.auto_merged?.reason),i=this._busy?"true":"false",n=O(e);return l`<div class="alert warning">
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
    </div>`}_renderInferredNotice(e){let r=this._busy?"true":"false",i=O(e);return l`<div class="alert warning">
      <ha-icon icon="mdi:package-variant-closed-check" aria-hidden="true"></ha-icon>
      <span class="grow">${Mi(e)}</span>
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
    </div>`}_renderFacts(e){let r=this.locale,i=E(e),n=se(e.window_start,e.window_end,r),o=x(e),a=e.restricted?null:Pt(e.tracking_url),d=e.tracking_number?.trim()??"",u=this._details?.orders??[],m=hn(this.snapshot?.parcels??[],e),g=this._details?.parcel.id===e.id?this._details.parcel:null,h=e.has_code?g?.pickup_code??null:null,_=this._returnsOf(e),f=(W,ss)=>l`<div><dt>${W}</dt><dd>${ss}</dd></div>`,v=e.status_timeless?V(e.status_time,r,we):"",I=e.status_undated?` \xB7 ${v?p(s.sinceDate,{date:v}):s.dateNotKnownInline}`:e.status_time?` \xB7 ${p(s.sinceDate,{date:H(e.status_time,r)})}`:"",R=Ii(e),oe=Pi(e);return l`<dl class="facts">
      ${f(s.status,`${U(e.status)}${I}`)}
      ${e.delivered_undated?f(s.delivered,e.delivered_timeless&&V(e.delivered_at,r,we)||s.dateNotKnown):e.delivered_at?f(s.delivered,H(e.delivered_at,r)):c}
      ${i?f(s.expected,`${M(i.start,i.end,r,No)}${R?` \xB7 ${R}`:""}`):c}
      ${n?f(s.timeWindow,n):c}
      ${_.length?f(s.returnBadge,l`<ul>
              ${_.map(W=>this._renderReturnLink(W))}
            </ul>`):c}
      ${o||a||!e.restricted?f(s.carrier,l`${o??(e.restricted?"":s.notKnownYet)}${a?l`<a class="link" href=${a} target="_blank" rel="noopener noreferrer">
                  ${s.trackOnline}<span class="sr-only"> ${s.opensInNewTab}</span>
                  <ha-icon icon="mdi:open-in-new" aria-hidden="true"></ha-icon>
                </a>`:c}`):c}
      ${d?l`<div>
            <dt><label for="tracking-number">${s.trackingNumber}</label></dt>
            <dd class="copy-row">
              <input id="tracking-number" readonly .value=${d} spellcheck="false" />
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
          </div>`:c}
      ${m.length?f(s.packagesInShipment,l`<ul class="packages">
              ${m.map(W=>this._renderPackage(W,e.id))}
            </ul>`):c}
      ${e.merchant?f(s.merchant,e.merchant):c}
      ${e.seller?f(s.seller,e.seller):c}
      ${oe?f(s.parcelAppName,oe):c}
      ${u.length?f(s.orders,l`<ul>
              ${u.map(W=>l`<li>
                    ${W.number}${W.placed_at?` \xB7 ${H(W.placed_at,r)}`:""}
                  </li>`)}
            </ul>`):e.order_numbers.length?f(s.orders,e.order_numbers.join(", ")):c}
      ${e.references.length?f(s.references,e.references.join(", ")):c}
      ${e.items.length?f(s.items,l`<ul>
              ${e.items.map(W=>l`<li>${W}</li>`)}
            </ul>`):c}
      ${e.pickup_point?f(s.pickupPoint,e.pickup_point):c}
      ${h?f(s.pickupCode,h):c}
      ${e.restricted?c:f(s.parcelId,e.id)}
    </dl>`}_renderReturnLink(e){let r=this.snapshot?.settings.today??"",i=`${Je(e,r)} \xB7 ${F(e.day,this.locale)}`;return e.restricted?l`<li>${i}</li>`:l`<li>
      <button
        type="button"
        class="link-btn"
        aria-haspopup="dialog"
        aria-disabled=${this._busy?"true":"false"}
        @click=${()=>this._openReturn(e.id)}
      >
        ${i}
      </button>
    </li>`}_openReturn(e){this._busy||(this.closeDialog(),this.dispatchEvent(new CustomEvent(_i,{detail:e})))}_renderPackage(e,r){let i=this.locale,n=e.tracking_number?.trim()||O(e),o=E(e),a=e.delivered_undated?e.delivered_timeless&&V(e.delivered_at,i,we)||s.dateNotKnownInline:e.delivered_at?H(e.delivered_at,i):o?M(o.start,o.end,i):"",d=[U(e.status),a].filter(Boolean).join(" \xB7 ");return e.id===r?l`<li aria-current="true" tabindex="-1" data-current-package>
        <strong>${n}</strong>${d?` \xB7 ${d}`:""}
      </li>`:l`<li>
      <button
        type="button"
        class="link-btn"
        aria-label=${p(s.showPackage,{name:n})}
        aria-disabled=${this._busy?"true":"false"}
        @click=${()=>this._switchTo(e.id)}
      >
        ${n}</button
      >${d?` \xB7 ${d}`:""}
    </li>`}_renderTimeline(e){if(!e.length)return l`<p class="muted">${s.noTimeline}</p>`;let r=this.locale;return l`<ol class="timeline">
      ${Fo(e).map(i=>{let n=U(i.status),o=i.label.trim(),d=[i.undated?i.timeless&&V(i.time,r,we)||s.dateNotKnown:H(i.time,r),ke(i.source)].filter(Boolean).join(" \xB7 ");return l`<li style=${B({"--dot-color":Ye(i.status)})}>
          <span class="dot" aria-hidden="true"></span>
          <div class="entry-title">${n}</div>
          ${o&&o!==n?l`<div>${o}</div>`:c}
          ${d?l`<div class="entry-meta">${d}</div>`:c}
        </li>`})}
    </ol>`}_renderDateForm(){let e=this._dateForm,r=this._formError,i=(n,o,a,d=!1)=>{let u=r?.field===n;return l`<label class="field">
        <span class="field-label">${o}</span>
        <input
          type=${a}
          name=${n}
          .value=${N(e[n])}
          ?data-first=${d}
          aria-invalid=${u?"true":"false"}
          aria-describedby=${u?"date-error":c}
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
          </div>`:c}
    </form>`}_renderMerge(e){let{pool:r,shown:i,target:n}=this._mergeChoice(e),o=r.likely.length+r.older.length;if(!o)return l`<p class="empty">${s.noMergeCandidates}</p>`;let a=this._mergeQuery.trim()!=="",d=o>Do,u=this._mergeOlder&&!a?r.likely.length:-1,m=!a&&!this._mergeOlder&&r.older.length>0;return l`<p id="merge-intro">${s.mergeIntro}</p>
      ${d?l`<label class="field">
            <span class="field-label">${s.mergeSearch}</span>
            <input
              type="search"
              data-first
              autocomplete="off"
              placeholder=${s.mergeSearchPlaceholder}
              .value=${N(this._mergeQuery)}
              @input=${this._onMergeQuery}
            />
          </label>`:c}
      <fieldset class="merge-list" aria-describedby="merge-intro">
        <legend class="sr-only">${s.mergeChoose}</legend>
        ${i.map((g,h)=>this._renderCandidate(g,e.id,{checked:g.id===n,first:!d&&h===0,olderFirst:h===u}))}
        ${a&&!i.length?l`<p class="empty">${s.mergeNoMatch}</p>`:c}
      </fieldset>
      ${m?l`<button
            type="button"
            class="link-btn"
            ?data-first=${!d&&!i.length}
            @click=${this._showOlderMerge}
          >
            ${p(s.mergeShowOlder,{count:String(r.older.length)})}
          </button>`:c}
      ${this._mergeHint&&!n?l`<p class="hint merge-hint" role="alert">${s.mergeChooseFirst}</p>`:c}`}_renderCandidate(e,r,i){return l`<label class="merge-option">
      <input
        type="radio"
        name="merge-target"
        value=${e.id}
        .checked=${N(i.checked)}
        ?data-first=${i.first}
        ?data-older-first=${i.olderFirst}
        @change=${this._onMergeTarget}
      />
      ${this._renderCandidateLines(e,r)}
    </label>`}_renderCandidateLines(e,r){let i=Me(e,this.locale),n=i.items?null:cn(Zi(this.snapshot?.merge_suggestions,e.id,r));return l`<span class="merge-lines">
      <span class="merge-line"><strong>${i.title}</strong> · ${i.when}</span>
      <span class="merge-line muted">${i.carrier}</span>
      ${i.emails?l`<span class="merge-line muted">${i.emails}</span>`:c}
      <span class="merge-line items ${i.items?"":"muted"}">
        ${i.items??i.noItems}
      </span>
      ${n?l`<span class="merge-line items" data-also>${n}</span>`:c}
    </span>`}_dayContext(){let e=this.snapshot?.settings;return{today:e?.today??"",timeZone:e?.time_zone??Intl.DateTimeFormat().resolvedOptions().timeZone}}_renderSplit(){return l`<fieldset aria-describedby="split-hint">
        <legend>${s.splitIntro}</legend>
        <div class="split-list">
          ${this._splitRows.map((e,r)=>l`<label class="check-row split-row">
              <input
                type="checkbox"
                .value=${e.lead}
                .checked=${N(this._splitSelection.includes(e.lead))}
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
              </button>`:c}
        </div>`}case"split":{let n=Xt(this._splitChosen,this._splitRows.length);return l`<div class="dialog-actions">
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
          ${kn(e,this.snapshot?.settings.user_is_admin===!0)?l`<button
                type="button"
                class="btn"
                data-check-again
                title=${s.checkAgainHint}
                aria-disabled=${r}
                @click=${this._checkAgain}
              >
                ${this._checking?s.checkingAgain:s.checkAgain}
              </button>`:c}
          <button type="button" class="btn" data-mode="merge" @click=${this._startMerge}>
            ${s.mergeWith}
          </button>
          ${n?l`<button type="button" class="btn" data-mode="split" @click=${this._startSplit}>
                ${s.split}
              </button>`:c}
          ${e.archived?c:l`<button
                type="button"
                class="btn danger"
                data-mode="archive"
                @click=${this._startArchive}
              >
                ${s.archive}
              </button>`}
          ${$e(e.status)?l`<span class="spacer"></span>
                <button
                  type="button"
                  class="btn primary"
                  aria-disabled=${r}
                  @click=${this._markDelivered}
                >
                  <ha-icon icon="mdi:check" aria-hidden="true"></ha-icon>${s.markDelivered}
                </button>`:c}
        </div>`}}}_setMode(e){this._mode=e,this._error=null,this._formError=null,this.focusAfterRender(e==="archive"?"[data-cancel]":"[data-first], [data-cancel]")}_backToView(){let e=this._mode;this._mode="view",this._error=null,this._formError=null,this.focusAfterRender(`[data-mode="${e}"]`)}_editDate(){let e=this._parcel;this._dateForm=e?ki(e):Un,this._setMode("date")}_startMerge(){this._mergeTarget="",this._mergeQuery="",this._mergeOlder=!1,this._mergeHint=!1,this._setMode("merge")}_startSplit(){this._splitSelection=[],this._setMode("split")}_startArchive(){this._setMode("archive")}_parcelService(e,r,i){let n=this.hass,o=this._parcel;!n||!o||this.runAction(()=>re(n,e,{parcel_id:o.id,...r}),i)}_confirm(){this._parcelService("update",{confirm:!0})}_undoMerge(){this._parcelService("undo_merge",{})}_keepMerge(){this._parcelService("update",{confirm_merge:!0})}_undoInferred(){this._parcelService("undo_delivery",{})}_keepInferred(){this._parcelService("update",{confirm_delivery:!0})}_markDelivered(){this._parcelService("mark_delivered",{})}async _checkAgain(){let e=this.hass,r=this._parcel;if(!e||!r||this._busy)return;let i=++this._checkRun,n=mr(null);this._checkStatus=null,this._checking=!0,await this.runAction(async()=>{let o=await j(e,"parcel/check_again",{parcel_id:r.id});n=mr(o)},()=>{let o=this.snapshot?.settings;this._checkStatus=$n(n,{enabled:o?.ai_enabled===!0,mode:o?.ai_mode??"off"})}),i===this._checkRun&&(this._checking=!1)}_dismissCheckStatus(){this._checkStatus=null}_archive(){this._parcelService("archive",{},()=>this.closeDialog())}_onPrivateClick(e){this._busy&&e.preventDefault()}_togglePrivate(e){let r=e.currentTarget.checked,i=this.hass,n=this._parcel;!i||!n||this._busy||(this._pendingPrivate=r,this.runAction(async()=>{try{await re(i,"update",{parcel_id:n.id,private:r})}catch(o){throw this._pendingPrivate=null,o}}))}_onDateInput(e){let r=e.currentTarget,i=r.name;this._dateForm={...this._dateForm,[i]:r.value},this._formError=null}_saveDate(e){e.preventDefault();let r=this._parcel;if(!r||this._busy)return;let i=this._dateForm,n=vt(i);if(n){this._formError=n,this.focusAfterRender(`[name="${n.field}"]`);return}let o=$i(r.id,i);this._parcelService("update",o,()=>this._backToView())}_mergePool(e){let r=this.snapshot;return r?Gi(r.parcels,e,this._dayContext()):{likely:[],older:[]}}_mergeChoice(e){let r=this._mergePool(e),i=this._mergeQuery.trim(),n=r.likely;i?n=Vi([...r.likely,...r.older],i):this._mergeOlder&&(n=[...r.likely,...r.older]);let o=n.some(a=>a.id===this._mergeTarget)?this._mergeTarget:"";return{pool:r,shown:n,target:o}}_onMergeTarget(e){this._mergeTarget=e.currentTarget.value,this._mergeHint=!1}_onMergeQuery(e){this._mergeQuery=e.currentTarget.value}_showOlderMerge(){this._mergeOlder=!0,this.focusAfterRender("[data-older-first]")}_acceptPossible(e){let r=this.hass;if(!r)return;let i=null;this.runAction(async()=>{let n=await j(r,"suggestion/accept",{suggestion_id:e.suggestionId,parcel_id:e.candidateId});i=typeof n?.parcel_id=="string"?n.parcel_id:null},()=>{i!==null&&i!==this._parcelId&&(this._parcelId=i,this._details=null,this._loadError=null,this._load()),this.focusAfterRender("[data-autofocus]")})}_dismissPossible(e){let r=this.hass;r&&this.runAction(()=>j(r,"suggestion/dismiss",{suggestion_id:e.suggestionId,parcel_id:e.candidateId}),()=>{this.focusAfterRender("[data-autofocus]")})}_merge(){let e=this.hass,r=this._parcel;if(!e||!r)return;let{target:i}=this._mergeChoice(r);if(!i){this._mergeHint=!0,this.focusAfterRender('input[name="merge-target"]');return}this.runAction(()=>re(e,"merge",{parcel_ids:[r.id,i]}),()=>this._backToView())}_onSplitChange(e){let r=e.currentTarget,i=this._splitSelection.filter(n=>n!==r.value);this._splitSelection=r.checked?[...i,r.value]:i}_split(){let e=this._splitRows,r=this._splitChosen;Xt(r,e.length)&&this._parcelService("split",{origins:En(e,r)},()=>this._backToView())}_onOriginsToggle(e){this._originsOpen=e.currentTarget.open}_toggleFold(e){let r=new Set(this._openFolds);r.delete(e)||r.add(e),this._openFolds=r}_dismissOriginNotice(){this._originNotice=null}_showParcel(e){e!==null&&this._switchTo(e)}async _focusOrigins(){if(await this.updateComplete,!this.isOpen)return;let e=this.renderRoot.querySelector("dialog [data-origins-summary]");e?e.focus():this.focusInDialog("[data-autofocus]")}_moveRow(e){let r=this.hass,i=this._parcel;if(!r||!i||this._busy)return;let n=i.id,o=null;this._originNotice=null,this.runAction(async()=>{o=await ai(r,"split",{parcel_id:n,origins:e.ids})},()=>{let a=o;this._originNotice={text:s.movedNotice,undo:a===null?null:()=>this._moveBack(n,a),show:a},this._load(),this._focusOrigins()})}_moveBack(e,r){let i=this.hass;!i||this._busy||this.runAction(()=>re(i,"merge",{parcel_ids:[e,r]}),()=>{this._originNotice={text:s.movedBackNotice,undo:null,show:null},this._load(),this._focusOrigins()})}_removeRow(e){let r=this.hass,i=this._parcel;if(!r||!i||this._busy)return;let n=i.id,o=null,a=!0;this._originNotice=null,this.runAction(async()=>{let d=await j(r,"origin/remove",{parcel_id:n,origin_id:e.lead});o=typeof d?.filtered_id=="string"?d.filtered_id:null,a=typeof d?.parcel_id=="string"},()=>{let d=o;this._originNotice={text:a?s.removedNotice:s.removedGoneNotice,undo:d===null?null:()=>this._restoreRow(d,n),show:null},a&&this._load(),this._focusOrigins()})}_restoreRow(e,r){let i=this.hass;if(!i||this._busy)return;let n=null,o=[];this.runAction(async()=>{let a=await j(i,"review/restore",{filtered_id:e});n=typeof a?.review_id=="string"?a.review_id:null;let d=a?.parcel_ids;o=Array.isArray(d)?d.filter(u=>typeof u=="string"):[]},()=>{let a=this._parcelId===r&&!this.snapshot?.parcels.some(u=>u.id===r),d=In({review:n,parcels:o},r,a);d.follow!==null&&(this._parcelId=d.follow,this._details=null,this._loadError=null),this._originNotice={text:Lo[d.notice],undo:null,show:d.show},this._load(),this._focusOrigins()})}async _copy(e){let r=e.currentTarget,i=this._parcel?.tracking_number?.trim();if(!i)return;this._copyState="idle";try{if(!navigator.clipboard?.writeText)throw new Error("Clipboard API unavailable");await navigator.clipboard.writeText(i),this._copyState="copied";return}catch{}let n=this.renderRoot.querySelector("#tracking-number");n?.focus(),n?.select();let o=!1;try{o=document.execCommand("copy")}catch{o=!1}this._copyState=o?"copied":"failed",o&&r.focus()}};z("parcels-details-dialog",fr);var gr=["all","active","recent","completed"],It={all:s.filterAll,active:s.filterActive,recent:s.filterRecent,completed:s.filterCompleted},Mt="parcels-filter",Ot="parcels-filter-changed";function _r(t){return typeof t=="string"&&gr.includes(t)}function Bn(){try{return globalThis.localStorage??null}catch{return null}}function Lt(t=Bn()){try{let e=t?.getItem(Mt);return _r(e)?e:"all"}catch{return"all"}}function jn(t,e=Bn(),r=globalThis.window??null){try{e?.setItem(Mt,t)}catch{}r?.dispatchEvent(new CustomEvent(Ot,{detail:t}))}function Ho(t,{today:e,timeZone:r}){let i=We(e),n=ie(i,6),o=d=>d!==null&&k(d,i)>=0&&k(d,n)<=0;if(o(C(t.status_time,r))||o(C(t.delivered_at,r)))return!0;let a=E(t);return a!==null&&k(a.start,n)<=0&&k(a.end,i)>=0}function zn(t,e,r){switch(e){case"active":return $e(t.status);case"completed":return!$e(t.status);case"recent":return Ho(t,r);default:return!0}}function Kn(t,e,{today:r}){switch(e){case"active":return!Se(t,r);case"completed":return Se(t,r);case"recent":{let i=We(r);return k(t.day,i)>=0&&k(t.day,ie(i,6))<=0}default:return!0}}var br=class extends ce{static properties={snapshot:{attribute:!1},locale:{attribute:!1},_returnId:{state:!0},_mode:{state:!0}};static styles=[K,Pe,S`
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
    `];constructor(){super(),this.snapshot=null,this.locale=Ie(void 0),this._returnId=null,this._mode="view"}async open(e,r=null){this._returnId=e,this._mode="view",await this.showDialog(r)}dialogClosed(){this._returnId=null,this._mode="view"}canLightDismiss(){return this._mode==="view"&&!this._busy}get _return(){let e=this._returnId;return e===null?null:this.snapshot?.returns.find(r=>r.id===e)??null}renderContent(){let e=this._return,r=this.snapshot?.settings.today??"";return l`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">
            ${e?Re(e):s.returnDetails}
          </h2>
          ${e?this._renderBadges(e,r):c}
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
          </div>`:c}
      ${e&&!e.restricted&&this.snapshot?.settings.user_is_admin===!0?this._renderActions():c}
    `}_renderBadges(e,r){return l`<div class="dialog-badges">
      <span class="badge return">
        <ha-icon icon=${Le} aria-hidden="true"></ha-icon>${Je(e,r)}
      </span>
      ${e.private||e.restricted?l`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${s.private}
          </span>`:c}
      ${e.archived?l`<span class="badge">${s.archived}</span>`:c}
    </div>`}_renderBody(e){return e?this._mode==="remove"?l`<p>${s.removeReturnQuestion}</p>`:l`<p class="hint">${s.returnHint}</p>
      ${this._renderFacts(e)}`:l`<p class="empty">${s.returnNotFound}</p>`}_renderFacts(e){let r=this.locale,i=(m,g)=>l`<div><dt>${m}</dt><dd>${g}</dd></div>`,n=cr(e.pickup_rule),o=e.restricted?null:x(e),a=e.restricted?null:Pt(e.tracking_url),d=e.tracking_number?.trim()??"",u=this._parcels(e);return l`<dl class="facts">
      ${e.pickup?i(s.pickup,l`${F(e.pickup,r)}${n?l`<div class="hint">${n}</div>`:c}`):c}
      ${e.started?i(s.returnStartedDay,H(e.started,r)):c}
      ${o||a?i(s.returnCarrier,l`${o??""}${a?l`<a class="link" href=${a} target="_blank" rel="noopener noreferrer">
                  ${s.trackOnline}<span class="sr-only"> ${s.opensInNewTab}</span>
                  <ha-icon icon="mdi:open-in-new" aria-hidden="true"></ha-icon>
                </a>`:c}`):c}
      ${d?i(s.trackingNumber,d):c}
      ${e.order_numbers.length?i(s.orders,e.order_numbers.join(", ")):c}
      ${e.items.length?i(s.items,l`<ul>
              ${e.items.map(m=>l`<li>${m}</li>`)}
            </ul>`):c}
      ${u.length?i(s.returnSentBackFrom,l`<ul>
              ${u.map(m=>this._renderParcel(m))}
            </ul>`):c}
      ${e.emails.length?i(s.returnEmails,this._renderEmails(e)):c}
    </dl>`}_parcels(e){let r=this.snapshot?.parcels??[];return e.parcel_ids.flatMap(i=>r.find(n=>n.id===i)??[])}_renderParcel(e){let r=O(e),i=e.delivered_undated?e.delivered_timeless&&V(e.delivered_at,this.locale,we)||s.dateNotKnownInline:e.delivered_at?H(e.delivered_at,this.locale):"",n=[U(e.status),i].filter(Boolean).join(" \xB7 ");return e.restricted?l`<li>${r} · ${n}</li>`:l`<li>
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
      ${e.emails.map(i=>{let n=i.label.trim(),o=[i.time?H(i.time,r):"",ke(i.source)].filter(Boolean).join(" \xB7 ");return l`<li>
          ${n?l`<div>${n}</div>`:c}
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
    </div>`}_startRemove(){this._mode="remove",this._error=null,this.focusAfterRender("[data-cancel]")}_backToView(){this._mode="view",this._error=null,this.focusAfterRender('[data-mode="remove"]')}_remove(){let e=this.hass,r=this._return;!e||!r||this.runAction(()=>j(e,"return/remove",{return_id:r.id}),()=>this.closeDialog())}_openParcel(e){this._busy||(this.closeDialog(),this.dispatchEvent(new CustomEvent(gi,{detail:e})))}};z("parcels-return-dialog",br);var Uo="parcels/subscribe",Wn=[2e3,1e4,3e4,6e4,3e5],Nt=new Map,Bo=0;function Gn(t,e){try{t(e)}catch(r){console.error(r)}}function qn(t,e){t.state=e;for(let r of[...t.listeners.values()])Gn(r,e)}function Vn(t){try{t().catch(()=>{})}catch{}}function Ft(t){t.retryTimer!==void 0&&(clearTimeout(t.retryTimer),t.retryTimer=void 0)}function Dt(t){t.connection.removeEventListener("ready",t.onReady),t.connection.removeEventListener("disconnected",t.onDisconnected)}function jo(t){Ft(t);let e=Wn[Math.min(t.retries,Wn.length-1)]??3e5;t.retries+=1,t.retryTimer=setTimeout(()=>{t.retryTimer=void 0,vr(t)},e)}function vr(t){if(t.released||t.unsubscribe||t.pending||t.listeners.size===0)return;Ft(t);let e=++t.attempt,r=t.epoch,i=()=>!t.released&&t.attempt===e;t.pending=!0;let n;try{n=t.connection.subscribeMessage(o=>{i()&&(t.retries=0,qn(t,{snapshot:Sn(o),error:null}))},{type:Uo},{resubscribe:!1})}catch(o){n=Promise.reject(o)}n.then(o=>{if(i()){t.pending=!1,t.unsubscribe=o;return}t.epoch===r&&Vn(o),t.released&&t.attempt===e+1&&(t.pending=!1,Dt(t))},o=>{i()?(t.pending=!1,qn(t,{snapshot:t.state.snapshot,error:q(o)}),jo(t)):t.released&&t.attempt===e+1&&(t.pending=!1,Dt(t))})}function zo(t,e){if(!t.listeners.delete(e)||t.listeners.size>0)return;t.released=!0,t.attempt+=1,Ft(t),Nt.get(t.connection)===t&&Nt.delete(t.connection);let r=t.unsubscribe;t.unsubscribe=null,r&&Vn(r),t.pending||Dt(t)}function Ko(t){let e={connection:t,listeners:new Map,state:{snapshot:null,error:null},epoch:0,attempt:0,unsubscribe:null,pending:!1,released:!1,retries:0,retryTimer:void 0,onReady:()=>{e.released||e.unsubscribe||(e.pending=!1,e.retries=0,vr(e))},onDisconnected:()=>{e.epoch+=1,e.attempt+=1,e.unsubscribe=null,e.pending=!1,Ft(e),e.released&&Dt(e)}};return e}function Yn(t,e){let r=++Bo,i=Nt.get(t);i?(i.listeners.set(r,e),(i.state.snapshot||i.state.error)&&Gn(e,i.state)):(i=Ko(t),Nt.set(t,i),i.listeners.set(r,e),t.addEventListener("ready",i.onReady),t.addEventListener("disconnected",i.onDisconnected),vr(i));let n=i,o=!0;return()=>{o&&(o=!1,zo(n,r))}}var Ht=class{snapshot=null;error=null;_host;_connection=null;_unsubscribe=null;_hostConnected=!1;constructor(e){this._host=e,e.addController(this)}setConnection(e){e!==this._connection&&(this._release(),this._connection=e,this.snapshot=null,this.error=null,this._hostConnected&&this._subscribe(),this._host.requestUpdate())}hostConnected(){this._hostConnected=!0,this._subscribe()}hostDisconnected(){this._hostConnected=!1,this._release()}_subscribe(){!this._connection||this._unsubscribe||(this._unsubscribe=Yn(this._connection,e=>{this.snapshot=e.snapshot??this.snapshot,this.error=e.error,this._host.requestUpdate()}))}_release(){let e=this._unsubscribe;this._unsubscribe=null,e?.()}};var tt=class extends Q{static properties={_actionError:{state:!0}};_snapshots=new Ht(this);_hass=void 0;_hassKey=null;_locale=null;_localeKey="";constructor(){super(),this._actionError=null}get hass(){return this._hass}set hass(e){this._hass=e,this._snapshots.setConnection(e?.connection??null),this.toggleAttribute("dark",e?.themes?.darkMode===!0);let r=JSON.stringify([e?.language,e?.locale?.language,e?.locale?.time_format,e?.locale?.time_zone,e?.config?.time_zone,e?.user?.is_admin,e?.themes?.darkMode]);r!==this._hassKey&&(this._hassKey=r,this.requestUpdate()),this.hassChanged()}hassChanged(){}get snapshot(){return this._snapshots.snapshot}get locale(){let e=this._snapshots.snapshot?.settings.time_zone,r=`${this._hassKey??""}|${e??""}`;return(!this._locale||r!==this._localeKey)&&(this._locale=Ie(this._hass,e),this._localeKey=r),this._locale}async callService(e,r,i){let n=this._hass;if(!n)return!1;this._actionError=null;try{return await re(n,e,r),!0}catch(o){return this._actionError=p(i,{message:q(o)}),!1}}renderBanners(){let{snapshot:e,error:r}=this._snapshots;return!r&&!this._actionError?c:l`<div class="banners">
      ${r?l`<div class="alert ${e?"warning":"error"}" role="alert">
            <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              ${p(e?s.refreshError:s.loadError,{message:r})}
            </span>
          </div>`:c}
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
          </div>`:c}
    </div>`}renderLoading(){return this._snapshots.error?c:l`<p class="empty" role="status">${s.loading}</p>`}showActionError(e){this._actionError=e}_dismissActionError(){this._actionError=null}},Ne=class extends tt{static properties={_busyParcels:{state:!0},_filter:{state:!0}};_focusedParcel=null;_focusedReturn=null;constructor(){super(),this._busyParcels=new Set,this._filter=Lt()}connectedCallback(){super.connectedCallback(),this._filter=Lt(),window.addEventListener(Ot,this._onFilterEvent),window.addEventListener("storage",this._onStorage),window.addEventListener("location-changed",this._onLocationChanged),window.addEventListener("popstate",this._onLocationChanged)}disconnectedCallback(){super.disconnectedCallback(),window.removeEventListener(Ot,this._onFilterEvent),window.removeEventListener("storage",this._onStorage),window.removeEventListener("location-changed",this._onLocationChanged),window.removeEventListener("popstate",this._onLocationChanged)}setFilter(e){this._filter=e,jn(e)}filterParcels(e,r){let i=this._filter;if(i==="all")return r;let n={today:e.settings.today,timeZone:e.settings.time_zone};return r.filter(o=>zn(o,i,n))}filterReturns(e,r){let i=this._filter;if(i==="all")return r;let n={today:e.settings.today};return r.filter(o=>Kn(o,i,n))}_candidates=null;possiblyFor(e){let r=this.snapshot;if(!r)return null;this._candidates?.snapshot!==r&&(this._candidates={snapshot:r,map:Yi(r.merge_suggestions)});let i=this._candidates.map,n=new Set(e.map(a=>a.id)),o=new Map;for(let a of e)for(let d of i.get(a.id)??[])n.has(d.id)||o.set(d.id,d);return o.size?ln([...o.values()]):null}_onFilterEvent=e=>{let r=e.detail;_r(r)&&(this._filter=r)};_onStorage=e=>{(e.key===null||e.key===Mt)&&(this._filter=Lt())};_onLocationChanged=()=>{this._openLinked()};_openLinked(){let e=this.snapshot;if(!e||!this.isConnected)return;let{pathname:r,search:i,hash:n}=window.location,o=Hn(i);if(o===i)return;window.history.replaceState(window.history.state,"",`${r}${o}${n}`);let a=Fn(i);if(a?.kind==="parcel"){let d=e.parcels.find(u=>u.id===a.id);d&&this.openDetails(d,null)}else if(a?.kind==="return"){let d=e.returns.find(u=>u.id===a.id);d&&this.openReturn(d,null)}}willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement,i=r instanceof HTMLElement?r.closest(".chip"):null;this._focusedParcel=i?.dataset.parcelId??null,this._focusedReturn=i?.dataset.returnId??null}updated(e){super.updated(e),this._restoreFocus(),this._openLinked()}_restoreFocus(){let e=this._focusedParcel,r=this._focusedReturn;if(this._focusedParcel=null,this._focusedReturn=null,this.shadowRoot?.activeElement||!yr())return;let i=e!==null?pr(e):r!==null?hr(r):null;i&&this.renderRoot.querySelector(i)?.focus()}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback], button.chip-main")}openDetails=(e,r)=>{this.renderRoot.querySelector("parcels-details-dialog")?.open(e.id,()=>{(r?.isConnected?r:this.renderRoot.querySelector(pr(e.id))??this.focusFallback())?.focus()})};openReturn=(e,r)=>{this.renderRoot.querySelector("parcels-return-dialog")?.open(e.id,()=>{(r?.isConnected?r:this.renderRoot.querySelector(hr(e.id))??this.focusFallback())?.focus()})};undoMerge=e=>{this._parcelAction(e.id,"undo_merge",{parcel_id:e.id},s.undoFailed)};keepMerge=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_merge:!0},s.keepFailed)};undoInferred=e=>{this._parcelAction(e.id,"undo_delivery",{parcel_id:e.id},s.undoInferredFailed)};keepInferred=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_delivery:!0},s.keepInferredFailed)};renderDetailsDialog(){return l`<parcels-details-dialog
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
    ></parcels-return-dialog>`}_opener(){let e=this.shadowRoot?.activeElement;return e instanceof HTMLElement?e:this.focusFallback()}_onOpenParcel(e){let r=this.snapshot?.parcels.find(n=>n.id===e.detail),i=this._opener();r&&i&&this.openDetails(r,i)}_onOpenReturn(e){let r=this.snapshot?.returns.find(n=>n.id===e.detail),i=this._opener();r&&i&&this.openReturn(r,i)}async _parcelAction(e,r,i,n){if(!this._busyParcels.has(e)){this._busyParcels=new Set([...this._busyParcels,e]);try{await this.callService(r,i,n)}finally{let o=new Set(this._busyParcels);o.delete(e),this._busyParcels=o}}}_onDialogError(e){this.showActionError(e.detail)}};function yr(){let t=document.activeElement;return!t||t===document.body}function wr(t){if(typeof t!="object"||t===null||Array.isArray(t))throw new Error(s.configInvalid);return t}function kr(t){let e=t.title;if(e!=null){if(typeof e!="string")throw new Error(s.configTitle);return e.trim()}}function $r(t){return typeof t.type=="string"?t.type:""}function xr(t){let e=wr(t),r=e.show_archived??!0;if(typeof r!="boolean")throw new Error(s.configShowArchived);return{type:$r(e),title:kr(e),show_archived:r}}function Sr(t){let e=wr(t);return{type:$r(e),title:kr(e)}}function Rr(t){let e=wr(t);return{type:$r(e),title:kr(e)}}function De(t,e){return t===void 0?e:t||null}function Wo(t,e){let r=C(t.status_time,e.timeZone);switch(t.status){case"cancelled":return null;case"delivered":{let n=C(t.delivered_at,e.timeZone)??r;return n?{kind:"delivered",from:n,to:n}:null}case"returned":return r?{kind:"returned",from:r,to:r}:null;case"ready_for_pickup":{let n=r??e.today;return{kind:"pickup",from:n,to:yi(n,e.today)}}default:break}let i=E(t);return i?{kind:"eta",from:i.start,to:i.end}:(t.status==="attempted"||t.status==="exception")&&r?{kind:"status",from:r,to:r}:null}function Tr(t){return t.type==="parcel"?t.parcel.id:`return:${t.ret.id}`}function Qn(t){return t.window_start??t.window_end??"~"}function rt(t,e){return t<e?-1:t>e?1:0}function qo(t,e){return rt(Qn(t.parcel),Qn(e.parcel))||rt(O(t.parcel).toLowerCase(),O(e.parcel).toLowerCase())||rt(t.parcel.id,e.parcel.id)}function Go(t,e){return rt(Re(t.ret).toLowerCase(),Re(e.ret).toLowerCase())||rt(t.ret.id,e.ret.id)}function Vo(t,e){let r=t.startCol-e.startCol||e.endCol-e.startCol-(t.endCol-t.startCol)||(t.type===e.type?0:t.type==="parcel"?-1:1);return r||(t.type==="parcel"&&e.type==="parcel"?qo(t,e):t.type==="return"&&e.type==="return"?Go(t,e):0)}function Zn(t,e,r,i,n=[]){let o=vi(e),a=ie(e,6),d=[];for(let h of t){if(h.archived&&!i.showArchived)continue;let _=Wo(h,r);!_||k(_.to,e)<0||k(_.from,a)>0||d.push({type:"parcel",parcel:h,members:[h],placement:_,startCol:Math.max(0,ue(e,_.from)),endCol:Math.min(6,ue(e,_.to)),continuesBefore:k(_.from,e)<0,continuesAfter:k(_.to,a)>0,lane:0})}let u=lr(d,h=>dr(h.parcel,h.placement.kind,h.placement.from,h.placement.to)).map(h=>({...h.reduce((f,v)=>Oe(v.parcel,f.parcel)<0?v:f),members:h.map(f=>f.parcel).sort(Oe)}));for(let h of n){if(h.archived&&!i.showArchived||k(h.day,e)<0||k(h.day,a)>0)continue;let _=ue(e,h.day);u.push({type:"return",ret:h,day:h.day,startCol:_,endCol:_,continuesBefore:!1,continuesAfter:!1,lane:0})}u.sort(Vo);let m=[];for(let h of u){let _=m.findIndex(f=>f<h.startCol);_===-1&&(_=m.length),m[_]=h.endCol,h.lane=_}let g=o.map((h,_)=>u.filter(f=>f.startCol<=_&&_<=f.endCol).sort((f,v)=>f.lane-v.lane));return{start:e,end:a,days:o,items:u,lanes:m.length,perDay:g,busy:g.map(h=>h.length>0)}}var Yo=600,Qo=616,Zo={weekday:"short"},Jo={day:"numeric"},Xo={weekday:"long",day:"numeric",month:"long"},ea={weekday:"long",day:"numeric",month:"short"},Ar=class extends Ne{static properties={_config:{state:!0},_weekOffset:{state:!0},_narrow:{state:!0},_refreshing:{state:!0}};static styles=[K,yt,S`
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
    `];_resizeObserver=null;_resizeFrame=0;_layoutCache=null;constructor(){super(),this._config=xr({}),this._weekOffset=0,this._narrow=!1,this._refreshing=!1}static getStubConfig(){return{}}setConfig(e){this._config=xr(e)}getCardSize(){let e=this._layout();return e?this._narrow?9+e.perDay.reduce((i,n)=>i+n.length,0):3+Math.max(1,e.lanes):4}getGridOptions(){return{columns:"full",rows:"auto",min_columns:6}}connectedCallback(){super.connectedCallback(),typeof ResizeObserver<"u"&&(this._resizeObserver??=new ResizeObserver(e=>{let r=e[e.length-1]?.contentRect.width??0;cancelAnimationFrame(this._resizeFrame),this._resizeFrame=requestAnimationFrame(()=>this._measure(r))}),this._resizeObserver.observe(this))}disconnectedCallback(){super.disconnectedCallback(),this._resizeObserver?.disconnect(),cancelAnimationFrame(this._resizeFrame)}firstUpdated(e){super.firstUpdated(e),this._measure(this.getBoundingClientRect().width)}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback]")}_measure(e){e<=0||(e<Yo?this._narrow=!0:e>=Qo&&(this._narrow=!1))}_monday(e){return ie(We(e.settings.today),7*this._weekOffset)}_layout(){let e=this.snapshot;if(!e)return null;let r=this._monday(e),i=this._config.show_archived,n=this._filter,o=this._layoutCache;if(o&&o.snapshot===e&&o.monday===r&&o.showArchived===i&&o.filter===n)return o.layout;let a=Zn(this.filterParcels(e,e.parcels),r,{today:e.settings.today,timeZone:e.settings.time_zone},{showArchived:i},this.filterReturns(e,e.returns));return this._layoutCache={snapshot:e,monday:r,showArchived:i,filter:n,layout:a},a}render(){let e=this.snapshot,r=this._layout(),i=De(this._config.title,s.defaultWeekTitle),n=r?M(r.start,r.end,this.locale,Ci):"";return l`<ha-card>
        <div class="header">
          <div class="heading">
            ${i?l`<h2 class="title">${i}</h2>`:c}
            ${n?l`<p class="range" aria-live="polite">${n}</p>`:c}
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
      ></parcels-add-dialog>`}_renderGrid(e,r,i){let n=this.locale,o=e.settings.today,a=r.items.length===0,u={"grid-template-columns":r.busy.map(m=>m||a?"minmax(0, 1fr)":"minmax(0, 0.6fr)").join(" "),"grid-template-rows":`auto repeat(${Math.max(1,r.lanes)}, auto)`};return l`<div
      class="grid"
      role="group"
      aria-label=${p(s.weekOf,{range:i})}
      style=${B(u)}
    >
      ${r.days.map((m,g)=>l`<div
            class="day-bg ${m===o?"today":""}"
            style=${B({"grid-column":String(g+1)})}
            aria-hidden="true"
          ></div>`)}
      ${r.days.map((m,g)=>l`<div
            class="day-head ${m===o?"today":""}"
            style=${B({"grid-column":String(g+1)})}
            aria-current=${m===o?"date":c}
          >
            <span class="dow" aria-hidden="true">${F(m,n,Zo)}</span>
            <span class="dom" aria-hidden="true">${F(m,n,Jo)}</span>
            <span class="sr-only">${F(m,n,Xo)}</span>
          </div>`)}
      ${a?l`<p class="week-empty">${this._emptyText()}</p>`:c}
      ${te(r.items,Tr,m=>this._chip(m,!1,{"grid-column":`${m.startCol+1} / ${m.endCol+2}`,"grid-row":String(m.lane+2)}))}
    </div>`}_renderStacked(e,r,i){let n=this.locale,o=e.settings.today,a=this._filter!=="all"&&r.items.length===0;return l`${a?l`<p class="week-empty stacked">${this._emptyText()}</p>`:c}
      <ol class="days" aria-label=${p(s.weekOf,{range:i})}>
      ${r.days.map((d,u)=>{let m=r.perDay[u]??[],g=d===o;return l`<li
          class="day ${m.length?"":"compact"} ${g?"today":""}"
          aria-current=${g?"date":c}
        >
          <p class="day-label">
            ${F(d,n,ea)}${g?l`<span class="badge info">${s.todayTag}</span>`:c}
          </p>
          ${m.length?l`<ul class="day-chips">
                ${te(m,Tr,h=>l`<li>${this._chip(h,!0,void 0,u)}</li>`)}
              </ul>`:l`<span class="muted">${s.noDeliveriesThisDay}</span>`}
        </li>`})}
    </ol>`}_chip(e,r,i,n){if(e.type==="return")return wn(e.ret,{locale:this.locale,today:this.snapshot?.settings.today??"",position:i,onOpen:this.openReturn});let o=e.continuesBefore&&(!r||n===e.startCol),a=e.continuesAfter&&(!r||n===e.endCol);return Tt(e.parcel,{locale:this.locale,placement:e.placement,continuesBefore:o,continuesAfter:a,showRange:r,members:e.members,possibly:this.possiblyFor(e.members),busy:e.members.some(d=>this._busyParcels.has(d.id)),position:i,onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge,onUndoInferred:this.undoInferred,onKeepInferred:this.keepInferred})}_renderFilters(){return l`<div class="filters" role="group" aria-label=${s.filterLabel}>
      ${gr.map(e=>l`<button
            type="button"
            class="filter-btn"
            aria-pressed=${this._filter===e?"true":"false"}
            title=${e==="recent"?s.filterRecentHint:c}
            @click=${()=>this.setFilter(e)}
          >
            ${It[e]}
          </button>`)}
    </div>`}_emptyText(){return this._filter==="all"?s.noDeliveriesThisWeek:s.filterEmptyWeek}_previousWeek(){this._weekOffset-=1}_nextWeek(){this._weekOffset+=1}_thisWeek(){this._weekOffset=0}async _refresh(){if(!this._refreshing){this._refreshing=!0;try{await this.callService("refresh",{},s.refreshFailed)}finally{this._refreshing=!1}}}_openAdd(e){let r=e.currentTarget;this.renderRoot.querySelector("parcels-add-dialog")?.open(()=>{r.isConnected&&r.focus()})}_onAddError(e){this.showActionError(e.detail)}};z("parcels-week-card",Ar);Ee("parcels-week-card",s.weekCardName,s.weekCardDescription);var Cr=class extends Ne{static properties={_config:{state:!0}};static styles=[K,yt,S`
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
    `];_listCache=null;constructor(){super(),this._config=Sr({})}static getStubConfig(){return{}}setConfig(e){this._config=Sr(e)}getCardSize(){let e=this._list()?.boxes;return e?1+Math.max(1,e.length):3}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}focusFallback(){return this.renderRoot.querySelector("button.chip-main")??this.renderRoot.querySelector(".content")}_list(){let e=this.snapshot;if(!e)return null;let r=this._filter,i=this._listCache;if(i?.snapshot===e&&i.filter===r)return i;let n=Ki(e.parcels),o=this.filterParcels(e,n);return this._listCache={snapshot:e,filter:r,boxes:un(o),hidden:n.length-o.length},this._listCache}render(){let e=this._list(),r=De(this._config.title,s.defaultListTitle);return l`<ha-card>
        ${r?l`<div class="header"><h2 class="title">${r}</h2></div>`:c}
        ${this.renderBanners()}
        <div class="content" tabindex="-1">
          ${e?this._renderList(e.boxes,e.hidden):this.renderLoading()}
        </div>
      </ha-card>
      ${this.renderDetailsDialog()} ${this.renderReturnDialog()}`}_renderFilterNote(e){return e===0||this._filter==="all"?c:l`<p class="filter-note">
      ${p(s.filterNote,{filter:It[this._filter]})} ·
      <button type="button" class="link-btn" @click=${this._showAll}>${s.filterShowAll}</button>
    </p>`}_showAll=()=>{this.setFilter("all")};_renderList(e,r){if(!e.length)return l`${this._renderFilterNote(r)}
        <p class="empty">${r>0?s.noUndatedMatch:s.noUndatedParcels}</p>`;let i=this.locale;return l`${this._renderFilterNote(r)}
      <ul class="list">
      ${te(e,n=>n.parcel.id,({parcel:n,members:o})=>l`<li>
            ${Tt(n,{locale:i,showStatus:!0,members:o,possibly:this.possiblyFor(o),busy:o.some(a=>this._busyParcels.has(a.id)),onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge,onUndoInferred:this.undoInferred,onKeepInferred:this.keepInferred})}
          </li>`)}
    </ul>`}};z("parcels-list-card",Cr);Ee("parcels-list-card",s.listCardName,s.listCardDescription);function ta(t,e,r){let i=t.get(e);return i==="pending"||i!==void 0&&i===r}function Ut(t,e,r){if(!e.size)return t;let i=t.filter(n=>!ta(e,n.id,r));return i.length===t.length?t:i}function Pr(t,e){let r=new Map(t);for(let i of e)r.set(i,"pending");return r}function Ir(t,e){let r=new Map(t);for(let i of e)r.delete(i);return r}function Mr(t,e,r,i){let n=new Map(t);for(let o of e)r&&i(o)?n.set(o,r):n.delete(o);return n}function Jn(t,e){let r=null;for(let[i,n]of t)n!=="pending"&&n!==e&&(r??=new Map(t),r.delete(i));return r??t}function Xn(t,e){if(t<=0)return null;let r=t===1?s.aiQueueOne:p(s.aiQueueMany,{count:t});if(e===null)return r;let i=Math.max(1,Math.round(e/60));return i<120?p(s.aiQueueMinutes,{queue:r,minutes:i}):p(s.aiQueueHours,{queue:r,hours:Math.round(i/60)})}function Er(t,e,r){return t<=0?null:t===1?e:p(r,{count:t})}function es(t){let e=[Er(t.added,s.trustAddedOne,s.trustAddedMany),Er(t.rechecking,s.trustRecheckOne,s.trustRecheckMany),Er(t.kept,s.trustKeptOne,s.trustKeptMany)].filter(r=>r!==null);return e.length?p(s.trustDoneWith,{domain:t.domain,parts:e.join(", ")}):p(s.trustDone,{domain:t.domain})}function ts(t){let e=[[s.checkHeaders,String(t.headers)]];return t.servers.length&&e.push([s.checkServers,t.servers.map(r=>r||s.checkNoServer).join(", ")]),t.originals>0&&e.push([s.checkOriginals,String(t.originals)]),t.used===null?(e.push([s.checkUsed,s.checkUsedNone]),e):(e.push([s.checkUsed,p(s.checkUsedHeader,{n:t.used+1})],["DKIM",t.dkim||s.checkNoResult],["DMARC",t.dmarc||s.checkNoResult],["SPF",t.spf||s.checkNoResult]),e)}function rs(t){let e=t.subject.trim();return e||(t.removed?s.removedFromParcel:s.noSubject)}var Fe=["review","filtered"],ra=new Set(["not_parcel","unknown"]),ia={weekday:"short",day:"numeric",month:"short"};function is(t){return A(t.received??t.created)??-1/0}function ns(t){return[...t].sort((e,r)=>is(r)-is(e)||(e.id<r.id?-1:e.id>r.id?1:0))}function na(t){return[...t].sort((e,r)=>(r.day??"").localeCompare(e.day??"")||(e.id<r.id?-1:e.id>r.id?1:0))}function Or(t,e){if(!t.has(e))return t;let r=new Map(t);return r.delete(e),r}var Lr=class extends tt{static properties={_config:{state:!0},_tab:{state:!0},_editing:{state:!0},_editForm:{state:!0},_editProblem:{state:!0},_busyItems:{state:!0},_itemErrors:{state:!0},_hidden:{state:!0},_confirmClearAll:{state:!0},_confirmTrust:{state:!0},_trustStatus:{state:!0}};static styles=[K,S`
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
    `];connectedWhileHidden=!0;_focusedItem=null;_listCache=null;_visibleCache=null;_clearingAll=!1;constructor(){super(),this._config=Rr({}),this._tab="review",this._editing=null,this._editForm=Jt(null),this._editProblem=null,this._busyItems=new Set,this._itemErrors=new Map,this._hidden=new Map,this._confirmClearAll=!1,this._confirmTrust=null,this._trustStatus=null}static getStubConfig(){return{}}setConfig(e){this._config=Rr(e)}getCardSize(){if(!this._visible())return 0;let e=this._visibleLists();if(!e)return 3;let r=this._tab==="review"?e.review.length+e.suggestions.length:e.filtered.length;return 2+2*Math.max(1,r)}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}hassChanged(){this._syncVisibility()}_visible(){let e=this.snapshot;return e?e.settings.user_is_admin:this.hass?.user?.is_admin===!0}_syncVisibility(){let e=!this._visible();this.hidden!==e&&(this.hidden=e,this.dispatchEvent(new CustomEvent("card-visibility-changed",{bubbles:!0,composed:!0,detail:{value:!e}})))}_lists(){let e=this.snapshot;return e?(this._listCache?.snapshot!==e&&(this._listCache={snapshot:e,review:ns(e.review),suggestions:na(e.merge_suggestions),filtered:ns(e.filtered)}),this._listCache):null}_visibleLists(){let e=this._lists();if(!e)return null;let r=this._hidden;if(this._visibleCache?.lists!==e||this._visibleCache.hidden!==r){let i=this.snapshot;this._visibleCache={lists:e,hidden:r,visible:{review:Ut(e.review,r,i),suggestions:Ut(e.suggestions,r,i),filtered:Ut(e.filtered,r,i)}}}return this._visibleCache.visible}_listed(e){let r=this._lists();return r?[...r.review,...r.suggestions,...r.filtered].some(i=>i.id===e):!1}willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement,i=r instanceof HTMLElement?r.closest("[data-item-id]"):null;if(i){let o=[...this.renderRoot.querySelectorAll("[data-item-id]")].filter(a=>!a.closest("[hidden]"));this._focusedItem={id:i.dataset.itemId??"",index:o.indexOf(i)}}else this._focusedItem=null;this._hidden=Jn(this._hidden,this.snapshot),this._confirmClearAll&&!this._visibleLists()?.filtered.length&&(this._confirmClearAll=!1,r instanceof HTMLElement&&r.closest(".confirm")&&this._focusAfterUpdate("#panel-filtered"));let n=this._lists();if(n){let o=new Set([...n.review,...n.suggestions,...n.filtered].map(a=>a.id));this._editing!==null&&!o.has(this._editing)&&(this._editing=null,this._editProblem=null);for(let a of this._itemErrors.keys())o.has(a)||(this._itemErrors=Or(this._itemErrors,a))}}updated(e){super.updated(e),this._syncVisibility();let r=this._focusedItem;if(this._focusedItem=null,!r||this.shadowRoot?.activeElement||!yr())return;let n=[...this.renderRoot.querySelector(`#panel-${this._tab}`)?.querySelectorAll("[data-item-id]")??[]];(n.find(a=>a.dataset.itemId===r.id)??n[Math.min(Math.max(r.index,0),n.length-1)]??this.renderRoot.querySelector(`#tab-${this._tab}`))?.focus()}render(){if(!this._visible())return c;let e=this._visibleLists(),r=De(this._config.title,s.defaultReviewTitle);return l`<ha-card>
      ${r?l`<div class="header"><h2 class="title">${r}</h2></div>`:c}
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
      ${Fe.map(n=>{let o=this._tab===n;return l`<button
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
    </div>`}_renderReviewList(e,r){let i=this.snapshot?.settings,n=i?Xn(i.ai_queue,i.ai_queue_seconds):null,o=n?l`<p class="hint queue-hint">${n}</p>`:c,a=l`<div class="trust-status" role="status">
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
          </div>`:c}
    </div>`;return!e.length&&!r.length?l`${a}${o}<p class="empty">${s.emptyReview}</p>`:l`${a}${o}<div class="items">
      ${te(r,d=>d.id,(d,u)=>this._renderMergeSuggestion(d,u))}
      ${te(e,d=>d.id,(d,u)=>this._renderReviewItem(d,u))}
    </div>`}_renderMergeSuggestion(e,r){let i=this.locale,o=this._busyItems.has(e.id)?"true":"false",a=`suggestion-subject-${r}`,d=Ze(e.parcel,i),u=$t(e.reason),m=this.snapshot?.settings,g=m?[...e.candidates].sort(ir(e.parcel,{today:m.today,timeZone:m.time_zone})):e.candidates;return l`<article
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
        ${p(s.suggestionTitle,{parcel:Me(e.parcel,i).title})}
      </h3>
      <p class="subject-lines">${this._renderLines(e.parcel)}</p>
      ${u?l`<p class="meta">${p(s.reasonIs,{reason:u})}</p>`:c}
      <p class="hint">${s.suggestionHint}</p>
      <ul class="candidates">
        ${g.map(h=>{let _=Ze(h,i);return l`<li class="candidate">
            <span class="grow">${this._renderLines(h)}</span>
            <button
              type="button"
              class="btn"
              aria-label=${p(s.mergeSuggestedLabel,{candidate:_,title:d})}
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
          aria-label=${p(s.keepApartLabel,{title:d})}
          aria-disabled=${o}
          @click=${()=>this._command(e.id,"suggestion/dismiss",{suggestion_id:e.id})}
        >
          ${s.keepApart}
        </button>
      </div>
    </article>`}_renderLines(e){let r=Me(e,this.locale);return l`<span class="block"><strong>${r.title}</strong> · ${r.when}</span>
      <span class="meta block">${r.carrier}</span>
      ${r.emails?l`<span class="meta block">${r.emails}</span>`:c}
      <span class="meta block items-line">${r.items??r.noItems}</span>`}_renderFilteredList(e){return l`<p class="hint filtered-hint">${s.filteredHint}</p>
      ${e.length?l`${this._renderClearAll()}
            <div class="items">
            ${te(e,r=>r.id,(r,i)=>this._renderFilteredItem(r,i))}
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
      </div>`}_renderHead(e,r,i=c){let n=rs({subject:e.subject,removed:e.removed===!0});return l`<div class="item-head">
        <span class="sender">${e.sender||e.sender_domain}</span>${i}
      </div>
      <h3 class="subject" id=${r}>${n}</h3>`}_renderError(e){let r=this._itemErrors.get(e);return r?l`<div class="alert error" role="alert">
          <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
          <span class="grow">${r}</span>
        </div>`:c}_renderReviewItem(e,r){let i=this.locale,n=this._busyItems.has(e.id),o=this._editing===e.id,a=`review-subject-${r}`,d=e.received??e.created,u=Oi(e.reason),m=[d?p(s.receivedOn,{date:H(d,i)}):"",e.mailbox_owner?p(s.mailboxOf,{owner:e.mailbox_owner}):"",u?p(s.reasonIs,{reason:u}):""].filter(Boolean),g=e.source==="ai"?l`<span class="badge ai" title=${s.aiSuggestionLabel}>
            ${s.aiBadge}<span class="sr-only">, ${s.aiSuggestionLabel}</span>
          </span>`:c;return l`<article
      class="item"
      tabindex="-1"
      data-item-id=${e.id}
      aria-labelledby=${a}
      aria-busy=${n?"true":"false"}
    >
      ${this._renderHead(e,a,g)}
      ${m.length?l`<p class="meta">${m.join(" \xB7 ")}</p>`:c}
      ${e.authenticated?c:l`<div class="alert warning">
            <ha-icon icon="mdi:shield-alert-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              <strong class="block">${s.unverifiedSender}</strong>
              ${e.trusted_sender?p(s.trustedSenderNote,{domain:e.sender_domain||e.sender}):s.unverifiedSenderHint}
            </span>
          </div>`}
      ${e.checks?this._renderChecks(e.checks):c}
      ${e.errors.length?this._renderFailedChecks(e.errors):c}
      ${e.notes.length?this._renderNotes(e.notes):c}
      ${o?this._renderEditForm(e,n):this._renderSuggestion(e.suggestion)}
      ${this._renderError(e.id)} ${o?c:this._renderReviewActions(e,n)}
    </article>`}_renderChecks(e){return l`<details class="checks">
      <summary>${s.senderChecks}</summary>
      <dl class="facts">
        ${ts(e).map(([r,i])=>l`<dt>${r}</dt><dd>${i}</dd>`)}
      </dl>
    </details>`}_renderFailedChecks(e){return l`<details class="checks">
      <summary>${s.failedChecks}</summary>
      <ul class="codes">
        ${e.map(r=>{let i=Di(r);return l`<li><code>${r}</code>${i?`: ${i}`:c}</li>`})}
      </ul>
    </details>`}_renderNotes(e){return l`<details class="checks">
      <summary>${s.aiNotes}</summary>
      <p class="hint">${s.aiNotesHint}</p>
      <ul class="codes">
        ${e.map(r=>{let i=Ni(r);return l`<li><code>${r}</code>${i?`: ${i}`:c}</li>`})}
      </ul>
    </details>`}_renderSuggestion(e){if(!e)return l`<p class="hint section-label">${s.noSuggestion}</p>`;let r=this.locale,i=E(e),n=[[s.fieldKind,Ve(e.kind)||null],[s.fieldMerchant,e.merchant],[s.fieldCarrier,x({carrier:e.carrier,carrier_name:null})],[s.fieldTrackingNumbers,e.tracking_numbers.join(", ")||null],[s.fieldOrderNumbers,e.order_numbers.join(", ")||null],[s.fieldReference,e.reference],[e.kind==="customer_return"?s.pickup:s.expected,i?M(i.start,i.end,r,ia):null],[s.timeWindow,se(e.window_start,e.window_end,r)],[s.pickupPoint,e.pickup_point],[s.pickupCode,e.pickup_code],[s.items,e.items.length?l`<ul>
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
          </button>`:c}
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
      ${e.trusted_sender||e.fill?c:l`<button
            type="button"
            class="btn"
            data-trust
            title=${p(s.trustSenderHint,{domain:n})}
            aria-disabled=${i}
            aria-expanded=${e.authenticated?c:this._confirmTrust===e.id?"true":"false"}
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
    ${this._confirmTrust===e.id?this._renderTrustConfirm(e,n,r):c}`}_renderTrustConfirm(e,r,i){let n=`trust-question-${e.id}`;return l`<div
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
    </div>`}_renderEditForm(e,r){let i=this._editForm,n=this._editProblem,o=Object.keys(ft).filter(u=>!ra.has(u)||u===i.kind);o.includes(i.kind)||o.unshift(i.kind);let a=mt();i.carrier&&!Object.hasOwn(de,i.carrier)&&a.unshift({id:i.carrier,name:i.carrier});let d=(u,m,g="text",h)=>{let _=n?.field===u,f=[_?"edit-error":"",h??""].filter(Boolean).join(" ");return l`<label class="field">
        <span class="field-label">${m}</span>
        <input
          type=${g}
          name=${u}
          autocomplete="off"
          .value=${N(i[u])}
          aria-invalid=${_?"true":"false"}
          aria-describedby=${f||c}
          @input=${this._onEditInput}
        />
      </label>`};return l`<form id="edit-form" class="edit-form" novalidate @submit=${this._submitEdit}>
      <div class="form-grid">
        <label class="field">
          <span class="field-label">${s.fieldKind}</span>
          <select name="kind" data-first @change=${this._onEditInput}>
            ${o.map(u=>l`<option value=${u} ?selected=${u===i.kind}>
                  ${Ve(u)||u}
                </option>`)}
          </select>
        </label>
        ${d("merchant",s.fieldMerchant)}
        <label class="field">
          <span class="field-label">${s.fieldCarrier}</span>
          <select name="carrier" @change=${this._onEditInput}>
            <option value="" ?selected=${i.carrier===""}>${s.carrierUnknown}</option>
            ${a.map(u=>l`<option value=${u.id} ?selected=${u.id===i.carrier}>
                  ${u.name}
                </option>`)}
          </select>
        </label>
        <div class="field">
          ${d("tracking_numbers",s.fieldTrackingNumbers,"text","edit-hint-tracking")}
          <p class="hint" id="edit-hint-tracking">${s.hintList}</p>
        </div>
        <div class="field">
          ${d("order_numbers",s.fieldOrderNumbers,"text","edit-hint-orders")}
          <p class="hint" id="edit-hint-orders">${s.hintList}</p>
        </div>
        ${d("reference",s.fieldReference)}
        ${d("eta_start",s.fieldEtaStart,"date")}
        ${d("eta_end",s.fieldEtaEnd,"date")}
        ${d("window_start",s.fieldWindowStart,"time")}
        ${d("window_end",s.fieldWindowEnd,"time")}
        ${d("pickup_point",s.fieldPickupPoint)}
        ${d("pickup_code",s.fieldPickupCode)}
        <label class="field wide">
          <span class="field-label">${s.fieldItems}</span>
          <textarea
            name="items"
            rows="3"
            .value=${N(i.items)}
            aria-describedby="edit-hint-items"
            @input=${this._onEditInput}
          ></textarea>
          <span class="hint" id="edit-hint-items">${s.hintItems}</span>
        </label>
      </div>
      ${n?l`<div class="alert error" id="edit-error" role="alert">
            <span class="grow">${n.message}</span>
          </div>`:c}
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
            ${p(s.receivedOn,{date:H(n,this.locale)})}
          </p>`:c}
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
    </article>`}_selectTab(e,r){this._tab=e,r&&this.updateComplete.then(()=>this.renderRoot.querySelector(`#tab-${e}`)?.focus())}_onTabClick(e){let r=e.currentTarget.dataset.tab;this._selectTab(r,!1)}_onTabKeyDown(e){let r=Fe.indexOf(this._tab),i=getComputedStyle(e.currentTarget).direction==="rtl",n;switch(e.key){case"ArrowRight":n=r+(i?-1:1);break;case"ArrowLeft":n=r+(i?1:-1);break;case"Home":n=0;break;case"End":n=Fe.length-1;break;default:return}e.preventDefault();let o=Fe[(n+Fe.length)%Fe.length];o&&this._selectTab(o,!0)}_focusAfterUpdate(e){this.updateComplete.then(()=>this.renderRoot.querySelector(e)?.focus())}_askClearAll(){this._confirmClearAll=!0,this._focusAfterUpdate("#clear-all-cancel")}_cancelClearAll(){this._confirmClearAll=!1,this._focusAfterUpdate("#clear-all")}_onConfirmKeyDown(e){e.key==="Escape"&&(e.preventDefault(),e.stopPropagation(),this._cancelClearAll())}async _clearAll(){let e=this.hass,r=this._visibleLists()?.filtered.map(i=>i.id)??[];if(!(!e||this._clearingAll||!r.length)){this._clearingAll=!0,this._confirmClearAll=!1,this._hidden=Pr(this._hidden,r),this._focusAfterUpdate("#panel-filtered");try{await j(e,"filtered/clear_all"),this._hidden=Mr(this._hidden,r,this.snapshot,i=>this._listed(i))}catch(i){this._hidden=Ir(this._hidden,r),this.showActionError(p(s.actionFailed,{message:q(i)}))}finally{this._clearingAll=!1}}}_focusInItem(e,r){this.updateComplete.then(()=>{let i=this.renderRoot.querySelector(`[data-item-id="${CSS.escape(e)}"]`);(i?.querySelector(r)??i)?.focus()})}_startEdit(e){this._busyItems.has(e.id)||(this._editing=e.id,this._editForm=Jt(e.suggestion),this._editProblem=null,this._itemErrors=Or(this._itemErrors,e.id),this._focusInItem(e.id,"[data-first]"))}_cancelEdit(e){this._editing=null,this._editProblem=null,this._focusInItem(e,"[data-edit]")}_onEditInput(e){let r=e.currentTarget,i=r.name;this._editForm={...this._editForm,[i]:r.value},this._editProblem=null}_submitEdit(e){e.preventDefault();let r=this._editing;if(r===null||this._busyItems.has(r))return;let i=vt(this._editForm);if(i){this._editProblem=i,this._focusInItem(r,`[name="${i.field}"]`);return}this._command(r,"review/accept",{review_id:r,overrides:Si(this._editForm)},{onSuccess:()=>{this._editing===r&&(this._editing=null)}})}_accept(e){this._command(e.id,"review/accept",{review_id:e.id})}_askTrust(e){if(!this._busyItems.has(e.id)){if(e.authenticated){this._trust(e);return}this._confirmTrust=e.id,this._focusInItem(e.id,"[data-trust-cancel]")}}_cancelTrust(e){this._confirmTrust=null,this._focusInItem(e,"[data-trust]")}_onTrustKeyDown(e,r){e.key==="Escape"&&(e.preventDefault(),e.stopPropagation(),this._cancelTrust(r))}async _trust(e){let r=e.sender_domain||e.sender;this._confirmTrust=null,this._trustStatus=null,this._focusInItem(e.id,"[data-trust]"),await this._command(e.id,"review/trust_sender",{review_id:e.id},{hide:!1,onSuccess:i=>{let n=i??{};this._trustStatus=es({domain:n.domain??r,added:n.added??0,rechecking:n.rechecking??0,kept:n.kept??0})}})}_dismissTrustStatus(){this._trustStatus=null}async _command(e,r,i,{hide:n=!0,onSuccess:o}={}){let a=this.hass;if(!(!a||this._busyItems.has(e)||this._hidden.has(e))){this._busyItems=new Set([...this._busyItems,e]),this._itemErrors=Or(this._itemErrors,e),n&&(this._hidden=Pr(this._hidden,[e]));try{let d=await j(a,r,i);n&&(this._hidden=Mr(this._hidden,[e],this.snapshot,u=>this._listed(u))),o?.(d)}catch(d){this._hidden=Ir(this._hidden,[e]);let u=p(s.actionFailed,{message:q(d)});this._listed(e)?this._itemErrors=new Map([...this._itemErrors,[e,u]]):this.showActionError(u)}finally{let d=new Set(this._busyItems);d.delete(e),this._busyItems=d}}}};z("parcels-review-card",Lr);Ee("parcels-review-card",s.reviewCardName,s.reviewCardDescription);
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
