var Ce=globalThis,Ae=Ce.ShadowRoot&&(Ce.ShadyCSS===void 0||Ce.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,lt=Symbol(),jt=new WeakMap,fe=class{constructor(e,r,i){if(this._$cssResult$=!0,i!==lt)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=r}get styleSheet(){let e=this.o,r=this.t;if(Ae&&e===void 0){let i=r!==void 0&&r.length===1;i&&(e=jt.get(r)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&jt.set(r,e))}return e}toString(){return this.cssText}},Wt=t=>new fe(typeof t=="string"?t:t+"",void 0,lt),w=(t,...e)=>{let r=t.length===1?t[0]:e.reduce((i,n,o)=>i+(a=>{if(a._$cssResult$===!0)return a.cssText;if(typeof a=="number")return a;throw Error("Value passed to 'css' function must be a 'css' function result: "+a+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(n)+t[o+1],t[0]);return new fe(r,t,lt)},Kt=(t,e)=>{if(Ae)t.adoptedStyleSheets=e.map(r=>r instanceof CSSStyleSheet?r:r.styleSheet);else for(let r of e){let i=document.createElement("style"),n=Ce.litNonce;n!==void 0&&i.setAttribute("nonce",n),i.textContent=r.cssText,t.appendChild(i)}},dt=Ae?t=>t:t=>t instanceof CSSStyleSheet?(e=>{let r="";for(let i of e.cssRules)r+=i.cssText;return Wt(r)})(t):t;var{is:oi,defineProperty:ai,getOwnPropertyDescriptor:li,getOwnPropertyNames:di,getOwnPropertySymbols:ci,getPrototypeOf:pi}=Object,Re=globalThis,Vt=Re.trustedTypes,ui=Vt?Vt.emptyScript:"",hi=Re.reactiveElementPolyfillSupport,ge=(t,e)=>t,ct={toAttribute(t,e){switch(e){case Boolean:t=t?ui:null;break;case Object:case Array:t=t==null?t:JSON.stringify(t)}return t},fromAttribute(t,e){let r=t;switch(e){case Boolean:r=t!==null;break;case Number:r=t===null?null:Number(t);break;case Object:case Array:try{r=JSON.parse(t)}catch{r=null}}return r}},qt=(t,e)=>!oi(t,e),Yt={attribute:!0,type:String,converter:ct,reflect:!1,useDefault:!1,hasChanged:qt};Symbol.metadata??=Symbol("metadata"),Re.litPropertyMetadata??=new WeakMap;var H=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,r=Yt){if(r.state&&(r.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((r=Object.create(r)).wrapped=!0),this.elementProperties.set(e,r),!r.noAccessor){let i=Symbol(),n=this.getPropertyDescriptor(e,i,r);n!==void 0&&ai(this.prototype,e,n)}}static getPropertyDescriptor(e,r,i){let{get:n,set:o}=li(this.prototype,e)??{get(){return this[r]},set(a){this[r]=a}};return{get:n,set(a){let p=n?.call(this);o?.call(this,a),this.requestUpdate(e,p,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??Yt}static _$Ei(){if(this.hasOwnProperty(ge("elementProperties")))return;let e=pi(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(ge("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(ge("properties"))){let r=this.properties,i=[...di(r),...ci(r)];for(let n of i)this.createProperty(n,r[n])}let e=this[Symbol.metadata];if(e!==null){let r=litPropertyMetadata.get(e);if(r!==void 0)for(let[i,n]of r)this.elementProperties.set(i,n)}this._$Eh=new Map;for(let[r,i]of this.elementProperties){let n=this._$Eu(r,i);n!==void 0&&this._$Eh.set(n,r)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let r=[];if(Array.isArray(e)){let i=new Set(e.flat(1/0).reverse());for(let n of i)r.unshift(dt(n))}else e!==void 0&&r.push(dt(e));return r}static _$Eu(e,r){let i=r.attribute;return i===!1?void 0:typeof i=="string"?i:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,r=this.constructor.elementProperties;for(let i of r.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Kt(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,r,i){this._$AK(e,i)}_$ET(e,r){let i=this.constructor.elementProperties.get(e),n=this.constructor._$Eu(e,i);if(n!==void 0&&i.reflect===!0){let o=(i.converter?.toAttribute!==void 0?i.converter:ct).toAttribute(r,i.type);this._$Em=e,o==null?this.removeAttribute(n):this.setAttribute(n,o),this._$Em=null}}_$AK(e,r){let i=this.constructor,n=i._$Eh.get(e);if(n!==void 0&&this._$Em!==n){let o=i.getPropertyOptions(n),a=typeof o.converter=="function"?{fromAttribute:o.converter}:o.converter?.fromAttribute!==void 0?o.converter:ct;this._$Em=n;let p=a.fromAttribute(r,o.type);this[n]=p??this._$Ej?.get(n)??p,this._$Em=null}}requestUpdate(e,r,i,n=!1,o){if(e!==void 0){let a=this.constructor;if(n===!1&&(o=this[e]),i??=a.getPropertyOptions(e),!((i.hasChanged??qt)(o,r)||i.useDefault&&i.reflect&&o===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,i))))return;this.C(e,r,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,r,{useDefault:i,reflect:n,wrapped:o},a){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??r??this[e]),o!==!0||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||i||(r=void 0),this._$AL.set(e,r)),n===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(r){Promise.reject(r)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[n,o]of this._$Ep)this[n]=o;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[n,o]of i){let{wrapped:a}=o,p=this[n];a!==!0||this._$AL.has(n)||p===void 0||this.C(n,void 0,o,p)}}let e=!1,r=this._$AL;try{e=this.shouldUpdate(r),e?(this.willUpdate(r),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(r)):this._$EM()}catch(i){throw e=!1,this._$EM(),i}e&&this._$AE(r)}willUpdate(e){}_$AE(e){this._$EO?.forEach(r=>r.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(r=>this._$ET(r,this[r])),this._$EM()}updated(e){}firstUpdated(e){}};H.elementStyles=[],H.shadowRootOptions={mode:"open"},H[ge("elementProperties")]=new Map,H[ge("finalized")]=new Map,hi?.({ReactiveElement:H}),(Re.reactiveElementVersions??=[]).push("2.1.2");var ut=globalThis,Gt=t=>t,Pe=ut.trustedTypes,Zt=Pe?Pe.createPolicy("lit-html",{createHTML:t=>t}):void 0,ht="$lit$",U=`lit$${Math.random().toFixed(9).slice(2)}$`,mt="?"+U,mi=`<${mt}>`,ee=document,_e=()=>ee.createComment(""),ve=t=>t===null||typeof t!="object"&&typeof t!="function",ft=Array.isArray,rr=t=>ft(t)||typeof t?.[Symbol.iterator]=="function",pt=`[ 	
\f\r]`,be=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Jt=/-->/g,Qt=/>/g,Q=RegExp(`>|${pt}(?:([^\\s"'>=/]+)(${pt}*=${pt}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Xt=/'/g,er=/"/g,ir=/^(?:script|style|textarea|title)$/i,gt=t=>(e,...r)=>({_$litType$:t,strings:e,values:r}),l=gt(1),kn=gt(2),Sn=gt(3),$=Symbol.for("lit-noChange"),c=Symbol.for("lit-nothing"),tr=new WeakMap,X=ee.createTreeWalker(ee,129);function nr(t,e){if(!ft(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return Zt!==void 0?Zt.createHTML(e):e}var sr=(t,e)=>{let r=t.length-1,i=[],n,o=e===2?"<svg>":e===3?"<math>":"",a=be;for(let p=0;p<r;p++){let d=t[p],u,m,h=-1,g=0;for(;g<d.length&&(a.lastIndex=g,m=a.exec(d),m!==null);)g=a.lastIndex,a===be?m[1]==="!--"?a=Jt:m[1]!==void 0?a=Qt:m[2]!==void 0?(ir.test(m[2])&&(n=RegExp("</"+m[2],"g")),a=Q):m[3]!==void 0&&(a=Q):a===Q?m[0]===">"?(a=n??be,h=-1):m[1]===void 0?h=-2:(h=a.lastIndex-m[2].length,u=m[1],a=m[3]===void 0?Q:m[3]==='"'?er:Xt):a===er||a===Xt?a=Q:a===Jt||a===Qt?a=be:(a=Q,n=void 0);let b=a===Q&&t[p+1].startsWith("/>")?" ":"";o+=a===be?d+mi:h>=0?(i.push(u),d.slice(0,h)+ht+d.slice(h)+U+b):d+U+(h===-2?p:b)}return[nr(t,o+(t[r]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),i]},ye=class t{constructor({strings:e,_$litType$:r},i){let n;this.parts=[];let o=0,a=0,p=e.length-1,d=this.parts,[u,m]=sr(e,r);if(this.el=t.createElement(u,i),X.currentNode=this.el.content,r===2||r===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(n=X.nextNode())!==null&&d.length<p;){if(n.nodeType===1){if(n.hasAttributes())for(let h of n.getAttributeNames())if(h.endsWith(ht)){let g=m[a++],b=n.getAttribute(h).split(U),y=/([.?@])?(.*)/.exec(g);d.push({type:1,index:o,name:y[2],strings:b,ctor:y[1]==="."?Le:y[1]==="?"?De:y[1]==="@"?Ie:re}),n.removeAttribute(h)}else h.startsWith(U)&&(d.push({type:6,index:o}),n.removeAttribute(h));if(ir.test(n.tagName)){let h=n.textContent.split(U),g=h.length-1;if(g>0){n.textContent=Pe?Pe.emptyScript:"";for(let b=0;b<g;b++)n.append(h[b],_e()),X.nextNode(),d.push({type:2,index:++o});n.append(h[g],_e())}}}else if(n.nodeType===8)if(n.data===mt)d.push({type:2,index:o});else{let h=-1;for(;(h=n.data.indexOf(U,h+1))!==-1;)d.push({type:7,index:o}),h+=U.length-1}o++}}static createElement(e,r){let i=ee.createElement("template");return i.innerHTML=e,i}};function te(t,e,r=t,i){if(e===$)return e;let n=i!==void 0?r._$Co?.[i]:r._$Cl,o=ve(e)?void 0:e._$litDirective$;return n?.constructor!==o&&(n?._$AO?.(!1),o===void 0?n=void 0:(n=new o(t),n._$AT(t,r,i)),i!==void 0?(r._$Co??=[])[i]=n:r._$Cl=n),n!==void 0&&(e=te(t,n._$AS(t,e.values),n,i)),e}var Me=class{constructor(e,r){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=r}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:r},parts:i}=this._$AD,n=(e?.creationScope??ee).importNode(r,!0);X.currentNode=n;let o=X.nextNode(),a=0,p=0,d=i[0];for(;d!==void 0;){if(a===d.index){let u;d.type===2?u=new se(o,o.nextSibling,this,e):d.type===1?u=new d.ctor(o,d.name,d.strings,this,e):d.type===6&&(u=new Oe(o,this,e)),this._$AV.push(u),d=i[++p]}a!==d?.index&&(o=X.nextNode(),a++)}return X.currentNode=ee,n}p(e){let r=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(e,i,r),r+=i.strings.length-2):i._$AI(e[r])),r++}},se=class t{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,r,i,n){this.type=2,this._$AH=c,this._$AN=void 0,this._$AA=e,this._$AB=r,this._$AM=i,this.options=n,this._$Cv=n?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,r=this._$AM;return r!==void 0&&e?.nodeType===11&&(e=r.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,r=this){e=te(this,e,r),ve(e)?e===c||e==null||e===""?(this._$AH!==c&&this._$AR(),this._$AH=c):e!==this._$AH&&e!==$&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):rr(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==c&&ve(this._$AH)?this._$AA.nextSibling.data=e:this.T(ee.createTextNode(e)),this._$AH=e}$(e){let{values:r,_$litType$:i}=e,n=typeof i=="number"?this._$AC(e):(i.el===void 0&&(i.el=ye.createElement(nr(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===n)this._$AH.p(r);else{let o=new Me(n,this),a=o.u(this.options);o.p(r),this.T(a),this._$AH=o}}_$AC(e){let r=tr.get(e.strings);return r===void 0&&tr.set(e.strings,r=new ye(e)),r}k(e){ft(this._$AH)||(this._$AH=[],this._$AR());let r=this._$AH,i,n=0;for(let o of e)n===r.length?r.push(i=new t(this.O(_e()),this.O(_e()),this,this.options)):i=r[n],i._$AI(o),n++;n<r.length&&(this._$AR(i&&i._$AB.nextSibling,n),r.length=n)}_$AR(e=this._$AA.nextSibling,r){for(this._$AP?.(!1,!0,r);e!==this._$AB;){let i=Gt(e).nextSibling;Gt(e).remove(),e=i}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},re=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,r,i,n,o){this.type=1,this._$AH=c,this._$AN=void 0,this.element=e,this.name=r,this._$AM=n,this.options=o,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=c}_$AI(e,r=this,i,n){let o=this.strings,a=!1;if(o===void 0)e=te(this,e,r,0),a=!ve(e)||e!==this._$AH&&e!==$,a&&(this._$AH=e);else{let p=e,d,u;for(e=o[0],d=0;d<o.length-1;d++)u=te(this,p[i+d],r,d),u===$&&(u=this._$AH[d]),a||=!ve(u)||u!==this._$AH[d],u===c?e=c:e!==c&&(e+=(u??"")+o[d+1]),this._$AH[d]=u}a&&!n&&this.j(e)}j(e){e===c?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},Le=class extends re{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===c?void 0:e}},De=class extends re{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==c)}},Ie=class extends re{constructor(e,r,i,n,o){super(e,r,i,n,o),this.type=5}_$AI(e,r=this){if((e=te(this,e,r,0)??c)===$)return;let i=this._$AH,n=e===c&&i!==c||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,o=e!==c&&(i===c||n);n&&this.element.removeEventListener(this.name,this,i),o&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},Oe=class{constructor(e,r,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=r,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){te(this,e)}},or={M:ht,P:U,A:mt,C:1,L:sr,R:Me,D:rr,V:te,I:se,H:re,N:De,U:Ie,B:Le,F:Oe},fi=ut.litHtmlPolyfillSupport;fi?.(ye,se),(ut.litHtmlVersions??=[]).push("3.3.3");var ar=(t,e,r)=>{let i=r?.renderBefore??e,n=i._$litPart$;if(n===void 0){let o=r?.renderBefore??null;i._$litPart$=n=new se(e.insertBefore(_e(),o),o,void 0,r??{})}return n._$AI(t),n};var bt=globalThis,E=class extends H{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let r=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=ar(r,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return $}};E._$litElement$=!0,E.finalized=!0,bt.litElementHydrateSupport?.({LitElement:E});var gi=bt.litElementPolyfillSupport;gi?.({LitElement:E});(bt.litElementVersions??=[]).push("4.2.2");var k={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},K=t=>(...e)=>({_$litDirective$:t,values:e}),C=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,r,i){this._$Ct=e,this._$AM=r,this._$Ci=i}_$AS(e,r){return this.update(e,r)}update(e,r){return this.render(...r)}};var{I:bi}=or,lr=t=>t;var cr=t=>t.strings===void 0,dr=()=>document.createComment(""),oe=(t,e,r)=>{let i=t._$AA.parentNode,n=e===void 0?t._$AB:e._$AA;if(r===void 0){let o=i.insertBefore(dr(),n),a=i.insertBefore(dr(),n);r=new bi(o,a,t,t.options)}else{let o=r._$AB.nextSibling,a=r._$AM,p=a!==t;if(p){let d;r._$AQ?.(t),r._$AM=t,r._$AP!==void 0&&(d=t._$AU)!==a._$AU&&r._$AP(d)}if(o!==n||p){let d=r._$AA;for(;d!==o;){let u=lr(d).nextSibling;lr(i).insertBefore(d,n),d=u}}}return r},V=(t,e,r=t)=>(t._$AI(e,r),t),_i={},Ne=(t,e=_i)=>t._$AH=e,pr=t=>t._$AH,Fe=t=>{t._$AR(),t._$AA.remove()};var ur=(t,e,r)=>{let i=new Map;for(let n=e;n<=r;n++)i.set(t[n],n);return i},B=K(class extends C{constructor(t){if(super(t),t.type!==k.CHILD)throw Error("repeat() can only be used in text expressions")}dt(t,e,r){let i;r===void 0?r=e:e!==void 0&&(i=e);let n=[],o=[],a=0;for(let p of t)n[a]=i?i(p,a):a,o[a]=r(p,a),a++;return{values:o,keys:n}}render(t,e,r){return this.dt(t,e,r).values}update(t,[e,r,i]){let n=pr(t),{values:o,keys:a}=this.dt(e,r,i);if(!Array.isArray(n))return this.ut=a,o;let p=this.ut??=[],d=[],u,m,h=0,g=n.length-1,b=0,y=o.length-1;for(;h<=g&&b<=y;)if(n[h]===null)h++;else if(n[g]===null)g--;else if(p[h]===a[b])d[b]=V(n[h],o[b]),h++,b++;else if(p[g]===a[y])d[y]=V(n[g],o[y]),g--,y--;else if(p[h]===a[y])d[y]=V(n[h],o[y]),oe(t,d[y+1],n[h]),h++,y--;else if(p[g]===a[b])d[b]=V(n[g],o[b]),oe(t,n[h],n[g]),g--,b++;else if(u===void 0&&(u=ur(a,b,y),m=ur(p,h,g)),u.has(p[h]))if(u.has(p[g])){let F=m.get(a[b]),at=F!==void 0?n[F]:null;if(at===null){let zt=oe(t,n[h]);V(zt,o[b]),d[b]=zt}else d[b]=V(at,o[b]),oe(t,n[h],at),n[F]=null;b++}else Fe(n[g]),g--;else Fe(n[h]),h++;for(;b<=y;){let F=oe(t,d[y+1]);V(F,o[b]),d[b++]=F}for(;h<=g;){let F=n[h++];F!==null&&Fe(F)}return this.ut=a,Ne(t,d),$}});var hr="important",vi=" !"+hr,A=K(class extends C{constructor(t){if(super(t),t.type!==k.ATTRIBUTE||t.name!=="style"||t.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(t){return Object.keys(t).reduce((e,r)=>{let i=t[r];return i==null?e:e+`${r=r.includes("-")?r:r.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${i};`},"")}update(t,[e]){let{style:r}=t.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(e)),this.render(e);for(let i of this.ft)e[i]==null&&(this.ft.delete(i),i.includes("-")?r.removeProperty(i):r[i]=null);for(let i in e){let n=e[i];if(n!=null){this.ft.add(i);let o=typeof n=="string"&&n.endsWith(vi);i.includes("-")||o?r.setProperty(i,o?n.slice(0,-11):n,o?hr:""):r[i]=n}}return $}});var T=K(class extends C{constructor(t){if(super(t),t.type!==k.PROPERTY&&t.type!==k.ATTRIBUTE&&t.type!==k.BOOLEAN_ATTRIBUTE)throw Error("The `live` directive is not allowed on child or event bindings");if(!cr(t))throw Error("`live` bindings can only contain a single expression")}render(t){return t}update(t,[e]){if(e===$||e===c)return e;let r=t.element,i=t.name;if(t.type===k.PROPERTY){if(e===r[i])return $}else if(t.type===k.BOOLEAN_ATTRIBUTE){if(!!e===r.hasAttribute(i))return $}else if(t.type===k.ATTRIBUTE&&r.getAttribute(i)===e+"")return $;return Ne(t),e}});var mr="parcels";function Y(t,e,r){return t.callService(mr,e,r,void 0,!1)}function He(t,e,r={}){return t.callWS({...r,type:`${mr}/${e}`})}var q={amazon:"Amazon Logistics",asendia:"Asendia",bpost:"bpost",brt:"BRT",cainiao:"Cainiao",chronopost:"Chronopost",colissimo:"Colissimo",correos:"Correos",correos_express:"Correos Express",ctt:"CTT",ctt_expresso:"CTT Expresso",deutsche_post:"Deutsche Post",dhl:"DHL",dpd:"DPD",evri:"Evri",fedex:"FedEx",gls:"GLS",hermes:"Hermes",inpost:"InPost",la_poste:"La Poste",mondial_relay:"Mondial Relay",mrw:"MRW",nacex:"Nacex",paack:"Paack",postnl:"PostNL",poste_italiane:"Poste Italiane",royal_mail:"Royal Mail",sda:"SDA",seur:"SEUR",tnt:"TNT",ups:"UPS",usps:"USPS",vinted_go:"Vinted Go",yunexpress:"YunExpress",other:"Other"};function Ue(){return Object.entries(q).filter(([t])=>t!=="other").map(([t,e])=>({id:t,name:e})).sort((t,e)=>t.name.localeCompare(e.name,"en",{sensitivity:"base"})).concat([{id:"other",name:q.other??"Other"}])}function fr(t){return Object.hasOwn(q,t)?q[t]??t:t}var s={weekCardName:"Parcels week",weekCardDescription:"A Monday to Sunday calendar of your parcel deliveries.",listCardName:"Parcels without a date",listCardDescription:"Active parcels that don't have a delivery date yet.",reviewCardName:"Parcels review",reviewCardDescription:"E-mails that need a decision before Parcels uses them. Only shown to administrators.",defaultWeekTitle:"Parcels",defaultListTitle:"No date yet",defaultReviewTitle:"Parcels review",loading:"Loading parcels\u2026",loadError:"Couldn't load parcels: {message}",refreshError:"Couldn't update parcels: {message}",unknownError:"Unknown error",close:"Close",cancel:"Cancel",save:"Save",dismissMessage:"Dismiss message",configInvalid:"Invalid configuration: expected a map of options.",configTitle:'Invalid configuration: "title" must be text.',configShowArchived:'Invalid configuration: "show_archived" must be true or false.',previousWeek:"Previous week",nextWeek:"Next week",today:"Today",goToToday:"Go to the current week",weekNavigation:"Week navigation",weekOf:"Week of {range}",refresh:"Check mailboxes now",refreshFailed:"Couldn't check the mailboxes: {message}",addParcel:"Add parcel",noDeliveriesThisWeek:"No deliveries this week",noDeliveriesThisDay:"No deliveries",todayTag:"Today",privateParcel:"Private parcel",unnamedParcel:"Parcel",aiBadge:"AI",aiBadgeLabel:"found by the local AI",privateLabel:"private",autoMerged:"Auto-merged \u2014 check",autoMergedLabel:"merged automatically, please check",undo:"Undo",undoMergeLabel:"Undo the automatic merge of {title}",undoFailed:"Couldn't undo the merge: {message}",keep:"Keep",keepMergeLabel:"Keep the automatic merge of {title}",keepFailed:"Couldn't keep the merge: {message}",inferred:"Delivery inferred \u2014 check",inferredLabel:"delivery inferred, please check",undoInferredLabel:"Undo the inferred delivery of {title}",undoInferredFailed:"Couldn't undo the delivery: {message}",keepInferredLabel:"Keep the inferred delivery of {title}",keepInferredFailed:"Couldn't keep the delivery: {message}",continuesBefore:"started before this week",continuesAfter:"continues after this week",deliveredOn:"delivered {date}",returnedOn:"returned {date}",expectedOn:"expected {date}",readyForPickupSince:"ready for pickup since {date}",statusOn:"{status} on {date}",windowFrom:"from {time}",windowUntil:"until {time}",noUndatedParcels:"Every active parcel has a delivery date.",tabReview:"Needs review",tabFiltered:"Filtered",tabCount:"{label} ({count})",possibleDuplicate:"Possible duplicate",suggestionTitle:"Same parcel as {parcel}?",suggestionHint:"Merge the parcel that is the same one, or keep them apart.",reasonIs:"Reason: {reason}",mergeSuggested:"Merge",mergeSuggestedLabel:"Merge {candidate} into {title}",keepApart:"Keep apart",keepApartLabel:"Keep {title} apart from these parcels",reviewTabs:"Review lists",emptyReview:"Nothing to review.",emptyFiltered:"No filtered e-mails.",filteredHint:"E-mails the local AI classed as not about a parcel.",receivedOn:"Received {date}",noSubject:"(no subject)",mailboxOf:"Mailbox: {owner}",unverifiedSender:"Unverified sender",unverifiedSenderHint:"This e-mail didn't pass the sender checks (DKIM/DMARC). Make sure it's genuine before you accept it.",aiSuggestionLabel:"read by the local AI",suggestion:"Suggestion",noSuggestion:"No suggestion. Use Edit to enter the details yourself.",accept:"Accept",acceptWithChanges:"Accept with changes",edit:"Edit",dismiss:"Dismiss",trustSender:"Trust this sender",trustSenderHint:"Treat e-mails from {domain} as a known sender from now on",ignoreSender:"Ignore this sender",ignoreSenderHint:"Skip e-mails from {domain} from now on",restore:"Restore",fieldKind:"Type",fieldMerchant:"Merchant",fieldCarrier:"Carrier",fieldTrackingNumber:"Tracking number",fieldTrackingNumbers:"Tracking numbers",fieldOrderNumbers:"Order numbers",fieldEtaStart:"Expected from",fieldEtaEnd:"Expected until",fieldWindowStart:"Time window from",fieldWindowEnd:"Time window until",fieldPickupPoint:"Pickup point",fieldPickupCode:"Pickup code",fieldItems:"Items",fieldPrivate:"Private (only the owners can see it)",hintList:"Separate with commas or new lines.",hintItems:"One per line.",carrierAuto:"Detect automatically",carrierUnknown:"Unknown",details:"Parcel details",status:"Status",sinceDate:"since {date}",carrier:"Carrier",trackOnline:"Track on the carrier's site",opensInNewTab:"(opens in a new tab)",trackingNumber:"Tracking number",copy:"Copy",copyTrackingNumber:"Copy the tracking number",copied:"Copied.",copyFailed:"Couldn't copy automatically. The number is selected, so you can copy it yourself.",merchant:"Merchant",orders:"Orders",items:"Items",expected:"Expected",timeWindow:"Time window",pickupPoint:"Pickup point",pickupCode:"Pickup code",delivered:"Delivered",timeline:"Timeline",noTimeline:"No events yet.",provisional:"Provisional",provisionalHint:"Made from an order e-mail. It's completed when the shipping e-mail arrives.",archived:"Archived",private:"Private",loadingDetails:"Loading details\u2026",detailsError:"Couldn't load the details: {message}",retry:"Try again",notFound:"This parcel no longer exists.",aiNotice:"Found by the local AI. Check the details, then confirm them.",confirm:"Confirm",confirmLabel:"Confirm the details the local AI found",mergedNotice:"Merged automatically ({reason}). Check that it's one parcel.",mergedNoticeNoReason:"Merged automatically. Check that it's one parcel.",inferredNotice:"Probably delivered: another parcel from this shop was delivered around the expected day. Undo if it hasn't arrived.",markDelivered:"Mark delivered",editDate:"Edit date",mergeWith:"Merge with\u2026",split:"Split\u2026",archive:"Archive",actions:"Actions",mergeIntro:"Choose the parcel to merge into this one.",mergeChoose:"Parcel",mergeConfirm:"Merge",noMergeCandidates:"There are no other active parcels to merge with.",splitIntro:"Choose what to move to a new parcel.",splitConfirm:"Split off",splitHint:"Choose at least one, but not all of them.",archiveQuestion:"Archive this parcel? It no longer counts as active.",dateEndBeforeStart:"The end date is before the start date.",dateEndWithoutStart:"Set a start date too.",windowEndBeforeStart:"The time window must end after it starts.",actionFailed:"That didn't work: {message}",addTitle:"Add parcel",addSubmit:"Add",trackingRequired:"Enter a tracking number."},gr={ordered:"Ordered",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",exception:"Problem with delivery",ready_for_pickup:"Ready for pickup",returned:"Returned",cancelled:"Cancelled"},Be={order:"Order confirmation",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",ready_for_pickup:"Ready for pickup",delayed:"Delayed",customs:"Held at customs",return:"Return",cancelled:"Cancelled",not_parcel:"Not about a parcel",unknown:"Unknown"},br={parser:"E-mail",ai:"Local AI",manual:"Added by hand",seventeentrack:"17TRACK",inferred:"Inferred from another delivery"},_r={unknown_sender:"Unknown sender",not_aligned:"The sender's domain isn't authenticated (DKIM/DMARC)",no_auth_header:"No authentication results in the e-mail",untrusted_authserv:"Authentication results from an unknown server",low_confidence:"Not sure about the details",unknown_format:"Unknown e-mail format",ai_suggestion:"Read by the local AI",ai_unavailable:"The local AI wasn't available",ai_rejected:"The local AI's answer didn't pass the checks",restored:"Moved back from Filtered"},vr={same_number:"same tracking number",same_merchant_eta:"same shop and delivery date",same_merchant_day:"same shop, delivered on the expected day",same_merchant_domain:"the shop's tracked shipment followed its order"};function f(t,e){return t.replace(/\{(\w+)\}/g,(r,i)=>Object.hasOwn(e,i)?String(e[i]):r)}function R(t){if(typeof t=="string"&&t.trim())return t;if(t&&typeof t=="object"){let e=t.message;if(typeof e=="string"&&e.trim())return e;let r=t.code;if(typeof r=="string"&&r.trim())return r}return s.unknownError}var yi=["a[href]","button:not([disabled])","input:not([disabled]):not([type='hidden'])","select:not([disabled])","textarea:not([disabled])","[tabindex]:not([tabindex='-1'])"].join(",");function $i(t){return[...t.querySelectorAll(yi)].filter(e=>!e.closest("[hidden], [inert]")&&e.getClientRects().length>0)}function yr(t,e){if(t.key!=="Tab"||t.altKey||t.ctrlKey||t.metaKey)return;let r=$i(e),i=r[0],n=r[r.length-1];if(!i||!n){t.preventDefault(),e.focus();return}let a=e.getRootNode().activeElement,p=a instanceof HTMLElement&&e.contains(a)&&a!==e;t.shiftKey&&(!p||a===i)?(t.preventDefault(),n.focus()):!t.shiftKey&&(!p||a===n)&&(t.preventDefault(),i.focus())}var wi="parcels-error",ae=class extends E{static properties={hass:{attribute:!1},_open:{state:!0},_busy:{state:!0},_error:{state:!0}};_returnFocus=null;_pressedBackdrop=!1;_hadFocus=!1;_session=0;constructor(){super(),this.hass=void 0,this._open=!1,this._busy=!1,this._error=null}render(){return l`<dialog
      aria-labelledby="dialog-title"
      @close=${this._onClose}
      @keydown=${this._onKeyDown}
      @pointerdown=${this._onPointerDown}
      @click=${this._onClick}
    >
      ${this._open?this.renderContent():c}
    </dialog>`}renderContent(){return c}canLightDismiss(){return!this._busy}dialogClosed(){}get isOpen(){return this._open}async showDialog(e){this._session+=1,this._returnFocus=e,this._open=!0,this._busy=!1,this._error=null,await this.updateComplete;let r=this._dialog();!r||!this._open||!this.isConnected||(r.open||r.showModal(),this.focusInDialog("[data-autofocus]"))}closeDialog(){let e=this._dialog();e?.open&&e.close(),this._finishClose(!0)}focusInDialog(e){this.renderRoot.querySelector(`dialog ${e}`)?.focus()}async focusAfterRender(e){await this.updateComplete,this._open&&this.focusInDialog(e)}async runAction(e,r){if(this._busy)return;let i=this._session;this._busy=!0,this._error=null;try{await e(),this._open&&this._session===i&&r?.()}catch(n){let o=f(s.actionFailed,{message:R(n)});this._open&&this._session===i?this._error=o:this.dispatchEvent(new CustomEvent(wi,{detail:o}))}finally{this._session===i&&(this._busy=!1)}}disconnectedCallback(){super.disconnectedCallback(),this._finishClose(!1)}willUpdate(e){this._hadFocus=this._open&&!!this.shadowRoot?.activeElement}updated(e){this._hadFocus&&this._open&&!this.shadowRoot?.activeElement&&this.focusInDialog("[data-autofocus]"),this._hadFocus=!1}_dialog(){return this.renderRoot.querySelector("dialog")}_finishClose(e){if(!this._open)return;let r=this._returnFocus;this._returnFocus=null,this._open=!1,this._busy=!1,this._error=null,this._pressedBackdrop=!1,this.dialogClosed(),e&&r?.()}_onClose(e){let r=e.currentTarget;e.target===r&&!r.open&&this._finishClose(!0)}_onKeyDown(e){yr(e,e.currentTarget)}_onPointerDown(e){this._pressedBackdrop=e.target===e.currentTarget}_onClick(e){let r=this._pressedBackdrop&&e.target===e.currentTarget;this._pressedBackdrop=!1,r&&this.canLightDismiss()&&this.closeDialog()}};var xi=/^(\d{4})-(\d{2})-(\d{2})$/,ki=/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)(?:[.,](\d+))?(Z|[+-]\d{2}(?::?\d{2})?)?$/i,Si=[31,28,31,30,31,30,31,31,30,31,30,31];function Ti(t){return t%4===0&&t%100!==0||t%400===0}function Ei(t,e){return e===2&&Ti(t)?29:Si[e-1]??0}function We(t){if(typeof t!="string")return null;let e=xi.exec(t);if(!e)return null;let r=Number(e[1]),i=Number(e[2]),n=Number(e[3]);return i<1||i>12||n<1||n>Ei(r,i)?null:{year:r,month:i,day:n}}function z(t){return We(t)!==null}function ze(t){let e=We(t);if(!e)throw new RangeError(`Not a YYYY-MM-DD date: ${t}`);return e}function je({year:t,month:e,day:r}){let i=e<=2?t-1:t,n=Math.floor(i/400),o=i-n*400,a=(e+9)%12,p=Math.floor((153*a+2)/5)+r-1,d=o*365+Math.floor(o/4)-Math.floor(o/100)+p;return n*146097+d-719468}function Ci(t){let e=t+719468,r=Math.floor(e/146097),i=e-r*146097,n=Math.floor((i-Math.floor(i/1460)+Math.floor(i/36524)-Math.floor(i/146096))/365),o=i-(365*n+Math.floor(n/4)-Math.floor(n/100)),a=Math.floor((5*o+2)/153),p=o-Math.floor((153*a+2)/5)+1,d=a<10?a+3:a-9;return{year:n+r*400+(d<=2?1:0),month:d,day:p}}function Ai({year:t,month:e,day:r}){return`${String(t).padStart(4,"0")}-${String(e).padStart(2,"0")}-${String(r).padStart(2,"0")}`}function le(t,e){return Ai(Ci(je(ze(t))+e))}function _t(t,e){return je(ze(e))-je(ze(t))}function Ri(t){return((je(ze(t))+3)%7+7)%7}function wr(t){return le(t,-Ri(t))}function xr(t){return Array.from({length:7},(e,r)=>le(t,r))}function P(t,e){return t<e?-1:t>e?1:0}function kr(t,e){return P(t,e)>=0?t:e}function M(t){if(typeof t!="string")return null;let e=ki.exec(t.trim());if(!e)return null;let[,r,i,n,o]=e;if(!r||!i||!z(r))return null;let a=n?`.${n.slice(0,3).padEnd(3,"0")}`:"",p="Z";if(o&&o.toUpperCase()!=="Z"){let u=o.slice(1).replace(":","").padEnd(4,"0");p=`${o[0]}${u.slice(0,2)}:${u.slice(2,4)}`}let d=Date.parse(`${r}T${i}${a}${p}`);return Number.isNaN(d)?null:d}var $r=new Map;function Pi(t){let e=$r.get(t);if(!e){let r={calendar:"gregory",numberingSystem:"latn",year:"numeric",month:"2-digit",day:"2-digit"};try{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:t})}catch{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:"UTC"})}$r.set(t,e)}return e}function $e(t,e){if(z(t))return t;let r=M(t);if(r===null)return null;let i="",n="",o="";for(let p of Pi(e).formatToParts(r))p.type==="year"?i=p.value:p.type==="month"?n=p.value:p.type==="day"&&(o=p.value);let a=`${i.padStart(4,"0")}-${n}-${o}`;return z(a)?a:null}function Mi(t){return[...new Set(t)]}function Sr(t){return Mi(t.split(/[\n,;]+/).map(e=>e.trim()).filter(Boolean))}function Li(t){return t.split(/\r?\n/).map(e=>e.trim()).filter(Boolean)}function D(t){let e=/^(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?$/.exec((t??"").trim());if(!e)return null;let r=Number(e[1]),i=Number(e[2]);return r>23||i>59?null:`${String(r).padStart(2,"0")}:${String(i).padStart(2,"0")}`}function L(t){let e=t.trim();return e||null}function Di(t,e){return e&&!t?s.dateEndWithoutStart:t&&e&&P(e,t)<0?s.dateEndBeforeStart:null}function Ii(t,e){let r=D(t),i=D(e);return r&&i&&i<=r?s.windowEndBeforeStart:null}function Tr(t){return{eta_start:t.eta_start??"",eta_end:t.eta_end??"",window_start:D(t.window_start)??"",window_end:D(t.window_end)??""}}function Ke(t){let e=Di(t.eta_start,t.eta_end);if(e)return{message:e,field:e===s.dateEndWithoutStart?"eta_start":"eta_end"};let r=Ii(t.window_start,t.window_end);return r?{message:r,field:"window_end"}:null}function Er(t,e){return{parcel_id:t,eta_start:L(e.eta_start),eta_end:L(e.eta_end),window_start:D(e.window_start),window_end:D(e.window_end)}}var Cr="shipped";function vt(t){return{kind:t?.kind||Cr,merchant:t?.merchant??"",carrier:t?.carrier??"",tracking_numbers:(t?.tracking_numbers??[]).join(", "),order_numbers:(t?.order_numbers??[]).join(", "),eta_start:t?.eta_start??"",eta_end:t?.eta_end??"",window_start:D(t?.window_start)??"",window_end:D(t?.window_end)??"",pickup_point:t?.pickup_point??"",pickup_code:t?.pickup_code??"",items:(t?.items??[]).join(`
`)}}function Ar(t){return{kind:t.kind.trim()||Cr,merchant:L(t.merchant),carrier:L(t.carrier),tracking_numbers:Sr(t.tracking_numbers),order_numbers:Sr(t.order_numbers),eta_start:L(t.eta_start),eta_end:L(t.eta_end),window_start:D(t.window_start),window_end:D(t.window_end),pickup_point:L(t.pickup_point),pickup_code:L(t.pickup_code),items:Li(t.items)}}function Rr(t){let e=t.tracking_number.trim();if(!e)return null;let r={tracking_number:e},i=L(t.carrier);i&&(r.carrier=i);let n=L(t.merchant);return n&&(r.merchant=n),t.private&&(r.private=!0),r}function yt(t,e){return t.length>0&&t.length<e}var Oi="https://github.com/fratei/ha-parcels";function I(t,e){customElements.get(t)||customElements.define(t,e)}function de(t,e,r){let i=window;Array.isArray(i.customCards)||(i.customCards=[]);let n=i.customCards;n.some(o=>o?.type===t)||n.push({type:t,name:e,description:r,preview:!0,documentationURL:Oi})}var O=w`
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
`,Ve=w`
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
  .chip-meta {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .chip-title {
    font-size: 0.875rem;
    font-weight: 500;
    line-height: 1.3;
  }
  .chip-meta {
    font-size: 0.75rem;
    line-height: 1.3;
    color: var(--secondary-text-color, #727272);
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
`,Ye=w`
  dialog {
    box-sizing: border-box;
    width: min(560px, calc(100vw - 32px));
    max-width: none;
    max-height: calc(100vh - 32px);
    max-height: calc(100dvh - 32px);
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
  .dialog-error {
    flex: none;
    padding: 0 24px;
  }
  .dialog-error .alert {
    margin: 0 0 12px;
  }
  .section-title {
    margin: 16px 0 8px;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--secondary-text-color, #727272);
  }
  @media (max-width: 600px) {
    dialog {
      width: 100vw;
      height: 100vh;
      height: 100dvh;
      max-height: none;
      margin: 0;
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
    .dialog-error {
      padding: 0 16px;
    }
  }
`;var Pr={tracking_number:"",carrier:"",merchant:"",private:!1},$t=class extends ae{static properties={_form:{state:!0},_missingNumber:{state:!0}};static styles=[O,Ye,w`
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
    `];constructor(){super(),this._form=Pr,this._missingNumber=!1}async open(e=null){this._form=Pr,this._missingNumber=!1,await this.showDialog(e)}canLightDismiss(){return!1}renderContent(){let e=this._form,r=this._missingNumber;return l`
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
              .value=${T(e.tracking_number)}
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
              ${Ue().map(i=>l`<option value=${i.id} ?selected=${e.carrier===i.id}>
                    ${i.name}
                  </option>`)}
            </select>
          </label>
          <label class="field">
            <span class="field-label">${s.fieldMerchant}</span>
            <input
              name="merchant"
              autocomplete="off"
              .value=${T(e.merchant)}
              @input=${this._onInput}
            />
          </label>
          <label class="check-row">
            <input
              type="checkbox"
              name="private"
              .checked=${T(e.private)}
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
    `}_onInput(e){let r=e.currentTarget,i=r.name,n=r instanceof HTMLInputElement&&r.type==="checkbox"?r.checked:r.value;this._form={...this._form,[i]:n},i==="tracking_number"&&this._missingNumber&&r.value.trim()&&(this._missingNumber=!1)}_submit(e){e.preventDefault();let r=this.hass;if(!r||this._busy)return;let i=Rr(this._form);if(!i){this._missingNumber=!0,this.focusAfterRender("#tracking-number");return}this.runAction(()=>Y(r,"add",i),()=>this.closeDialog())}};I("parcels-add-dialog",$t);var wt=K(class extends C{constructor(t){if(super(t),t.type!==k.ATTRIBUTE||t.name!=="class"||t.strings?.length>2)throw Error("`classMap()` can only be used in the `class` attribute and must be the only part in the attribute.")}render(t){return" "+Object.keys(t).filter(e=>t[e]).join(" ")+" "}update(t,[e]){if(this.st===void 0){this.st=new Set,t.strings!==void 0&&(this.nt=new Set(t.strings.join(" ").split(/\s/).filter(i=>i!=="")));for(let i in e)e[i]&&!this.nt?.has(i)&&this.st.add(i);return this.render(e)}let r=t.element.classList;for(let i of this.st)i in e||(r.remove(i),this.st.delete(i));for(let i in e){let n=!!e[i];n===this.st.has(i)||this.nt?.has(i)||(n?(r.add(i),this.st.add(i)):(r.remove(i),this.st.delete(i)))}return $}});function Ni(t){try{return Intl.DateTimeFormat.supportedLocalesOf([t]),t}catch{return"en"}}function Fi(){let t=new Intl.DateTimeFormat(void 0,{hour:"numeric"}).resolvedOptions().hourCycle;return t==="h11"||t==="h12"}function Ge(t,e){let r=Ni(t?.locale?.language||t?.language||"en"),i=t?.locale?.time_format,n;i==="12"?n=!0:i==="24"?n=!1:i==="system"&&(n=Fi());let o=t?.locale?.time_zone==="local"?void 0:e||t?.config?.time_zone||void 0;return{language:r,hour12:n,timeZone:o}}var Mr=new Map;function we(t,e,r){let i=e.hour!==void 0||e.timeStyle!==void 0,n={...e,timeZone:r?"UTC":t.timeZone};i&&t.hour12!==void 0&&(n.hour12=t.hour12);let o=JSON.stringify([t.language,n]),a=Mr.get(o);if(!a){try{a=new Intl.DateTimeFormat(t.language,n)}catch{a=new Intl.DateTimeFormat(t.language,{...n,timeZone:void 0})}Mr.set(o,a)}return a}function xt(t){let e=We(t);return e?new Date(Date.UTC(e.year,e.month-1,e.day)):null}var Lr={weekday:"short",day:"numeric",month:"short"},Dr={day:"numeric",month:"short",year:"numeric"};function ie(t,e,r=Lr){let i=xt(t);return i?we(e,r,!0).format(i):t}function N(t,e,r,i=Lr){let n=xt(t),o=xt(e);return!n||!o?[t,e].filter(Boolean).join(" \u2013 "):t===e?we(r,i,!0).format(n):we(r,i,!0).formatRange(n,o)}function qe(t,e){let r=/^(\d{1,2}):(\d{2})/.exec(t);if(!r)return t;let i=new Date(Date.UTC(1970,0,1,Number(r[1]),Number(r[2])));return we(e,{hour:"numeric",minute:"2-digit"},!0).format(i)}function ce(t,e,r){return t&&e?`${qe(t,r)}\u2013${qe(e,r)}`:t?f(s.windowFrom,{time:qe(t,r)}):e?f(s.windowUntil,{time:qe(e,r)}):null}function j(t,e){if(!t)return"";let r=M(t);return r===null?t:we(e,{dateStyle:"medium",timeStyle:"short"},!1).format(r)}function xe(t){if(typeof t!="string")return null;let e=t.trim();return e||null}function Ir(t){let e=t.trim();if(!/^[a-z0-9]+(?:[_-][a-z0-9]+)*$/.test(e))return e;let r=e.replace(/[_-]+/g," ");return r.charAt(0).toUpperCase()+r.slice(1)}function ke(t,e){let r=xe(e);return r?Object.hasOwn(t,r)?t[r]??r:Ir(r):""}function pe(t){let e=xe(t.carrier_name);if(e)return e;let r=xe(t.carrier);return!r||r==="other"?null:Object.hasOwn(q,r)?fr(r):Ir(r)}function x(t){return t.restricted?s.privateParcel:xe(t.merchant)??pe(t)??xe(t.tracking_number)??s.unnamedParcel}function Ze(t){let e=pe(t);return e&&e!==x(t)?e:null}function G(t){return ke(gr,t)}function kt(t){return ke(Be,t)}function St(t){return ke(br,t)}function Or(t){return ke(_r,t)}function Je(t){return ke(vr,t)}var Qe="var(--secondary-text-color, #727272)",Nr="var(--info-color, #039be5)",Hi="var(--warning-color, #ffa600)",Ui="var(--success-color, #43a047)",Fr="var(--error-color, #db4437)",Bi="var(--purple-color, #926bc7)",Hr={ordered:Qe,shipped:Nr,in_transit:Nr,out_for_delivery:Hi,delivered:Ui,attempted:Fr,exception:Fr,ready_for_pickup:Bi,returned:Qe,cancelled:Qe};function Se(t){return Object.hasOwn(Hr,t)?Hr[t]:Qe}var zi=new Set(["delivered","returned","cancelled"]);function Xe(t){return!zi.has(t)}function W(t){let e=z(t.eta_start)?t.eta_start:null,r=z(t.eta_end)?t.eta_end:null,i=e??r;return i?{start:i,end:r&&P(r,i)>=0?r:i}:null}function Ur(t){return Xe(t.status)}function Br(t,e){let r=M(t.status_time),i=M(e.status_time);return r!==i?r===null?1:i===null?-1:i-r:t.id<e.id?-1:t.id>e.id?1:0}function zr(t){return t.filter(e=>Ur(e)&&!e.archived&&W(e)===null).sort(Br)}function et(t,e){return t.filter(r=>r.id!==e&&Ur(r)&&!r.archived&&!r.restricted).sort(Br)}function jr(t,e,r){return e?.kind==="delivered"||e?.kind==="returned"?null:ce(t.window_start,t.window_end,r)}function Wr(t,e){let r=e.placement??null,i=[];if(e.showStatus){let a=G(t.status);a&&i.push(a)}let n=Ze(t);n&&i.push(n),e.showRange&&r&&r.from!==r.to&&i.push(N(r.from,r.to,e.locale));let o=jr(t,r,e.locale);return o&&i.push(o),i.join(" \xB7 ")}function Kr(t,e){let{locale:r}=e,i=e.placement??null,n=[x(t)],o=Ze(t);o&&n.push(o);let a=G(t.status),p=i?ie(i.from,r):"";switch(i?.kind){case"delivered":n.push(f(s.deliveredOn,{date:p}));break;case"returned":n.push(f(s.returnedOn,{date:p}));break;case"pickup":n.push(f(s.readyForPickupSince,{date:p}));break;case"status":n.push(f(s.statusOn,{status:a,date:p}));break;case"eta":a&&n.push(a),n.push(f(s.expectedOn,{date:N(i.from,i.to,r)}));break;default:a&&n.push(a);break}let d=jr(t,i,r);return d&&n.push(d),t.restricted||(t.ai&&n.push(s.aiBadgeLabel),t.auto_merged&&n.push(s.autoMergedLabel),t.inferred&&n.push(s.inferredLabel)),(t.private||t.restricted)&&n.push(s.privateLabel),e.continuesBefore&&n.push(s.continuesBefore),e.continuesAfter&&n.push(s.continuesAfter),n.join(", ")}function Te(t,e){let r=[x(t)],i=Ze(t);i&&r.push(i);let n=t.tracking_number?.trim();n&&n!==r[0]&&r.push(n);let o=W(t);return r.push(o?N(o.start,o.end,e):G(t.status)),r.filter(Boolean).join(" \xB7 ")}function Tt(t){return`.chip[data-parcel-id="${CSS.escape(t)}"] button.chip-main`}function Vr(t,e,r,i){let n=e?"true":"false";return l`<div class="merge-note">
    <ha-icon icon=${t.icon} aria-hidden="true"></ha-icon>
    <span class="merge-label">${t.label}</span>
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
  </div>`}function ji(t,e,r){return Vr({icon:"mdi:call-merge",label:s.autoMerged,undoLabel:f(s.undoMergeLabel,{title:e}),keepLabel:f(s.keepMergeLabel,{title:e})},r.busy,()=>r.onUndoMerge(t),()=>r.onKeepMerge(t))}function Wi(t,e,r){return Vr({icon:"mdi:package-variant-closed-check",label:s.inferred,undoLabel:f(s.undoInferredLabel,{title:e}),keepLabel:f(s.keepInferredLabel,{title:e})},r.busy,()=>r.onUndoInferred(t),()=>r.onKeepInferred(t))}function tt(t,e){let{locale:r}=e,i=e.placement??null,n=x(t),o=Kr(t,{locale:r,placement:i,continuesBefore:e.continuesBefore,continuesAfter:e.continuesAfter}),a=Wr(t,{locale:r,placement:i,showStatus:e.showStatus,showRange:e.showRange}),p={chip:!0,"cont-before":e.continuesBefore===!0,"cont-after":e.continuesAfter===!0,returned:t.status==="returned"},d={...e.position,"--chip-color":Se(t.status)},u=l`<span class="chip-row" aria-hidden=${t.restricted?"true":c}>
    ${e.continuesBefore?l`<span class="cont">‹</span>`:c}
    ${t.status==="delivered"?l`<span class="check">✓</span>`:c}
    <span class="chip-text">
      <span class="chip-title">${n}</span>
      ${a?l`<span class="chip-meta">${a}</span>`:c}
    </span>
    ${t.ai&&!t.restricted?l`<span class="badge ai">${s.aiBadge}</span>`:c}
    ${t.private||t.restricted?l`<ha-icon class="lock" icon="mdi:lock"></ha-icon>`:c}
    ${e.continuesAfter?l`<span class="cont">›</span>`:c}
  </span>`;return t.restricted?l`<div class=${wt(p)} style=${A(d)}>
      <div class="chip-main" title=${o}>
        <span class="sr-only">${o}</span>
        ${u}
      </div>
    </div>`:l`<div class=${wt(p)} style=${A(d)} data-parcel-id=${t.id}>
    <button
      type="button"
      class="chip-main"
      aria-haspopup="dialog"
      aria-label=${o}
      title=${o}
      @click=${m=>e.onOpen(t,m.currentTarget)}
    >
      ${u}
    </button>
    ${t.auto_merged?ji(t,n,e):c}
    ${t.inferred?Wi(t,n,e):c}
  </div>`}function S(t){return typeof t=="object"&&t!==null&&!Array.isArray(t)}function _(t){return typeof t=="string"?t:null}function v(t){return typeof t=="string"?t:""}function Z(t){return Array.isArray(t)?t.filter(e=>typeof e=="string"):[]}function ne(t){return typeof t=="string"&&t!==""?t:null}function J(t,e){if(!Array.isArray(t))return[];let r=[];for(let i of t){let n=e(i);n!==null&&r.push(n)}return r}function Et(t){return t==="ai"||t==="manual"||t==="seventeentrack"?t:"parser"}function Ki(t){return!S(t)||!ne(t.origin)?null:{origin:v(t.origin),at:v(t.at),reason:v(t.reason)}}function rt(t){if(!S(t))return null;let e=ne(t.id);return e?{id:e,merchant:_(t.merchant),carrier:_(t.carrier),carrier_name:_(t.carrier_name),tracking_number:_(t.tracking_number),tracking_url:_(t.tracking_url),status:v(t.status),status_time:_(t.status_time),eta_start:_(t.eta_start),eta_end:_(t.eta_end),window_start:_(t.window_start),window_end:_(t.window_end),delivered_at:_(t.delivered_at),inferred:t.inferred===!0,pickup_point:_(t.pickup_point),pickup_code:_(t.pickup_code),order_numbers:Z(t.order_numbers),items:Z(t.items),private:t.private===!0,owners:Z(t.owners),source:Et(t.source),ai:t.ai===!0,auto_merged:Ki(t.auto_merged),provisional:t.provisional===!0,archived:t.archived===!0,origins:Z(t.origins),restricted:t.restricted===!0}:null}function Vi(t){return S(t)?{kind:v(t.kind),merchant:_(t.merchant),carrier:_(t.carrier),tracking_numbers:Z(t.tracking_numbers),order_numbers:Z(t.order_numbers),eta_start:_(t.eta_start),eta_end:_(t.eta_end),window_start:_(t.window_start),window_end:_(t.window_end),pickup_point:_(t.pickup_point),pickup_code:_(t.pickup_code),items:Z(t.items)}:null}function Yi(t){if(!S(t))return null;let e=ne(t.id);return e?{id:e,created:v(t.created),received:_(t.received),sender:v(t.sender),sender_domain:v(t.sender_domain),subject:v(t.subject),mailbox_owner:_(t.mailbox_owner),reason:v(t.reason),authenticated:t.authenticated===!0,source:t.source==="ai"?"ai":"parser",suggestion:Vi(t.suggestion)}:null}function qi(t){if(!S(t))return null;let e=ne(t.id);return e?{id:e,created:v(t.created),received:_(t.received),sender:v(t.sender),sender_domain:v(t.sender_domain),subject:v(t.subject)}:null}function Gi(t){if(!S(t))return null;let e=ne(t.id),r=rt(t.parcel),i=J(t.candidates,rt);return!e||!r||!i.length?null:{id:e,reason:v(t.reason),merchant:_(t.merchant),day:z(t.day)?t.day:null,parcel:r,candidates:i}}function Zi(t){return t==="suggest"||t==="auto"?t:"off"}function Ji(t,e=Date.now()){let r=S(t)?t:{},i=ne(r.time_zone)??"UTC",n=z(r.today)?r.today:$e(new Date(e).toISOString(),i)??"1970-01-01";return{user_is_admin:r.user_is_admin===!0,ai_enabled:r.ai_enabled===!0,ai_mode:Zi(r.ai_mode),dashboard_url:v(r.dashboard_url),seventeentrack:r.seventeentrack===!0,time_zone:i,today:n}}function Yr(t,e=Date.now()){let r=S(t)?t:{};return{parcels:J(r.parcels,rt),review:J(r.review,Yi),merge_suggestions:J(r.merge_suggestions,Gi),filtered:J(r.filtered,qi),settings:Ji(r.settings,e)}}function Qi(t){return S(t)?{time:v(t.time),status:v(t.status),source:t.source==="inferred"?"inferred":Et(t.source),label:v(t.label)}:null}function Xi(t){return S(t)?{id:v(t.id),merchant:_(t.merchant),number:v(t.number),placed_at:_(t.placed_at),parcel_ids:Z(t.parcel_ids)}:null}function en(t){if(!S(t))return null;let e=ne(t.id);return e?{id:e,label:v(t.label),source:Et(t.source),time:_(t.time)}:null}function qr(t){if(!S(t))return null;let e=rt(t.parcel);return e?{parcel:e,timeline:J(t.timeline,Qi),orders:J(t.orders,Xi),origins:J(t.origins,en)}:null}function Gr(t){if(typeof t!="string")return null;let e=t.trim();if(!e)return null;let r;try{r=new URL(e)}catch{return null}return r.protocol!=="https:"||!r.hostname||r.username||r.password?null:r.href}var tn={weekday:"short",day:"numeric",month:"short",year:"numeric"},Zr={eta_start:"",eta_end:"",window_start:"",window_end:""};function rn(t){return t.map((e,r)=>({entry:e,index:r,time:M(e.time)??-1/0})).sort((e,r)=>r.time-e.time||r.index-e.index).map(({entry:e})=>e)}var Ct=class extends ae{static properties={snapshot:{attribute:!1},locale:{attribute:!1},_parcelId:{state:!0},_details:{state:!0},_loading:{state:!0},_loadError:{state:!0},_mode:{state:!0},_copyState:{state:!0},_dateForm:{state:!0},_formError:{state:!0},_mergeTarget:{state:!0},_splitSelection:{state:!0},_pendingPrivate:{state:!0}};static styles=[O,Ye,w`
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
    `];_request=0;_loadedKey="";constructor(){super(),this.snapshot=null,this.locale=Ge(void 0),this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._copyState="idle",this._dateForm=Zr,this._formError=null,this._mergeTarget="",this._splitSelection=[],this._pendingPrivate=null}async open(e,r=null){this._parcelId=e,this._details=null,this._loadError=null,this._mode="view",this._copyState="idle",this._formError=null,this._pendingPrivate=null,this._load(),await this.showDialog(r)}dialogClosed(){this._request+=1,this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._pendingPrivate=null}canLightDismiss(){return this._mode==="view"&&!this._busy}willUpdate(e){if(super.willUpdate(e),!e.has("snapshot")||!this.isOpen||!this.snapshot)return;this._pendingPrivate=null;let r=this.snapshot.parcels.find(i=>i.id===this._parcelId);r&&JSON.stringify(r)!==this._loadedKey&&this._load()}get _parcel(){let e=this._parcelId;return e===null?null:this.snapshot?this.snapshot.parcels.find(r=>r.id===e)??null:this._details?.parcel??null}async _load(){let e=this.hass,r=this._parcelId;if(!e||r===null)return;let i=++this._request,n=this.snapshot?.parcels.find(o=>o.id===r);this._loadedKey=n?JSON.stringify(n):"",this._loading=!0,this._loadError=null;try{let o=await He(e,"get",{parcel_id:r});if(i!==this._request)return;let a=qr(o);if(!a)throw new Error(s.unknownError);this._details=a}catch(o){i===this._request&&(this._loadError=R(o))}finally{i===this._request&&(this._loading=!1)}}renderContent(){let e=this._parcel;return l`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">
            ${e?x(e):s.details}
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
      ${e&&!e.restricted?this._renderActions(e):c}
    `}_renderBadges(e){return l`<div class="dialog-badges">
      <span class="badge" style=${A({"--badge-color":Se(e.status)})}>
        ${G(e.status)}
      </span>
      ${e.ai&&!e.restricted?l`<span class="badge ai" title=${s.aiBadgeLabel}>
            ${s.aiBadge}<span class="sr-only">, ${s.aiBadgeLabel}</span>
          </span>`:c}
      ${e.private||e.restricted?l`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${s.private}
          </span>`:c}
      ${e.provisional?l`<span class="badge info">${s.provisional}</span>`:c}
      ${e.archived?l`<span class="badge">${s.archived}</span>`:c}
    </div>`}_renderBody(e){if(!e)return this.snapshot||!this._loading&&!this._loadError?l`<p class="empty">${s.notFound}</p>`:this._renderLoadState();switch(this._mode){case"date":return this._renderDateForm();case"merge":return this._renderMerge(e);case"split":return this._renderSplit();case"archive":return l`<p>${s.archiveQuestion}</p>`;default:return this._renderView(e)}}_renderLoadState(){return this._loadError?l`<div class="alert error" role="alert">
        <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
        <span class="grow">${f(s.detailsError,{message:this._loadError})}</span>
        <button type="button" class="btn" @click=${this._load}>${s.retry}</button>
      </div>`:l`<p class="empty" role="status">${s.loadingDetails}</p>`}_renderView(e){let r=e.restricted;return l`
      ${!r&&e.ai?l`<div class="alert">
            <ha-icon icon="mdi:robot-outline" aria-hidden="true"></ha-icon>
            <span class="grow">${s.aiNotice}</span>
            <button
              type="button"
              class="btn"
              aria-label=${s.confirmLabel}
              aria-disabled=${this._busy?"true":"false"}
              @click=${this._confirm}
            >
              ${s.confirm}
            </button>
          </div>`:c}
      ${!r&&e.auto_merged?this._renderMergeNotice(e):c}
      ${!r&&e.inferred?this._renderInferredNotice(e):c}
      ${!r&&e.provisional?l`<p class="hint">${s.provisionalHint}</p>`:c}
      ${this._renderFacts(e)}
      ${r?c:l`<label class="check-row switch-row">
            <input
              type="checkbox"
              role="switch"
              .checked=${T(this._pendingPrivate??e.private)}
              aria-disabled=${this._busy?"true":"false"}
              @click=${this._onPrivateClick}
              @change=${this._togglePrivate}
            />
            <span>${s.fieldPrivate}</span>
          </label>`}
      <h3 class="section-title">${s.timeline}</h3>
      ${this._details?this._renderTimeline(this._details.timeline):this._renderLoadState()}
    `}_renderMergeNotice(e){let r=Je(e.auto_merged?.reason),i=this._busy?"true":"false",n=x(e);return l`<div class="alert warning">
      <ha-icon icon="mdi:call-merge" aria-hidden="true"></ha-icon>
      <span class="grow">
        ${r?f(s.mergedNotice,{reason:r}):s.mergedNoticeNoReason}
      </span>
      <button
        type="button"
        class="btn"
        aria-label=${f(s.undoMergeLabel,{title:n})}
        aria-disabled=${i}
        @click=${this._undoMerge}
      >
        ${s.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${f(s.keepMergeLabel,{title:n})}
        aria-disabled=${i}
        @click=${this._keepMerge}
      >
        ${s.keep}
      </button>
    </div>`}_renderInferredNotice(e){let r=this._busy?"true":"false",i=x(e);return l`<div class="alert warning">
      <ha-icon icon="mdi:package-variant-closed-check" aria-hidden="true"></ha-icon>
      <span class="grow">${s.inferredNotice}</span>
      <button
        type="button"
        class="btn"
        aria-label=${f(s.undoInferredLabel,{title:i})}
        aria-disabled=${r}
        @click=${this._undoInferred}
      >
        ${s.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${f(s.keepInferredLabel,{title:i})}
        aria-disabled=${r}
        @click=${this._keepInferred}
      >
        ${s.keep}
      </button>
    </div>`}_renderFacts(e){let r=this.locale,i=W(e),n=ce(e.window_start,e.window_end,r),o=pe(e),a=e.restricted?null:Gr(e.tracking_url),p=e.tracking_number?.trim()??"",d=this._details?.orders??[],u=(h,g)=>l`<div><dt>${h}</dt><dd>${g}</dd></div>`,m=e.status_time?` \xB7 ${f(s.sinceDate,{date:j(e.status_time,r)})}`:"";return l`<dl class="facts">
      ${u(s.status,`${G(e.status)}${m}`)}
      ${e.delivered_at?u(s.delivered,j(e.delivered_at,r)):c}
      ${i?u(s.expected,N(i.start,i.end,r,tn)):c}
      ${n?u(s.timeWindow,n):c}
      ${o||a?u(s.carrier,l`${o??""}${a?l`<a class="link" href=${a} target="_blank" rel="noopener noreferrer">
                  ${s.trackOnline}<span class="sr-only"> ${s.opensInNewTab}</span>
                  <ha-icon icon="mdi:open-in-new" aria-hidden="true"></ha-icon>
                </a>`:c}`):c}
      ${p?l`<div>
            <dt><label for="tracking-number">${s.trackingNumber}</label></dt>
            <dd class="copy-row">
              <input id="tracking-number" readonly .value=${p} spellcheck="false" />
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
      ${e.merchant?u(s.merchant,e.merchant):c}
      ${d.length?u(s.orders,l`<ul>
              ${d.map(h=>l`<li>
                    ${h.number}${h.placed_at?` \xB7 ${j(h.placed_at,r)}`:""}
                  </li>`)}
            </ul>`):e.order_numbers.length?u(s.orders,e.order_numbers.join(", ")):c}
      ${e.items.length?u(s.items,l`<ul>
              ${e.items.map(h=>l`<li>${h}</li>`)}
            </ul>`):c}
      ${e.pickup_point?u(s.pickupPoint,e.pickup_point):c}
      ${e.pickup_code?u(s.pickupCode,e.pickup_code):c}
    </dl>`}_renderTimeline(e){if(!e.length)return l`<p class="muted">${s.noTimeline}</p>`;let r=this.locale;return l`<ol class="timeline">
      ${rn(e).map(i=>{let n=G(i.status),o=i.label.trim(),a=[j(i.time,r),St(i.source)].filter(Boolean).join(" \xB7 ");return l`<li style=${A({"--dot-color":Se(i.status)})}>
          <span class="dot" aria-hidden="true"></span>
          <div class="entry-title">${n}</div>
          ${o&&o!==n?l`<div>${o}</div>`:c}
          ${a?l`<div class="entry-meta">${a}</div>`:c}
        </li>`})}
    </ol>`}_renderDateForm(){let e=this._dateForm,r=this._formError,i=(n,o,a,p=!1)=>{let d=r?.field===n;return l`<label class="field">
        <span class="field-label">${o}</span>
        <input
          type=${a}
          name=${n}
          .value=${T(e[n])}
          ?data-first=${p}
          aria-invalid=${d?"true":"false"}
          aria-describedby=${d?"date-error":c}
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
    </form>`}_renderMerge(e){let r=et(this.snapshot?.parcels??[],e.id);if(!r.length)return l`<p class="empty">${s.noMergeCandidates}</p>`;let i=this._resolvedMergeTarget(r);return l`<p>${s.mergeIntro}</p>
      <label class="field">
        <span class="field-label">${s.mergeChoose}</span>
        <select data-first @change=${this._onMergeTarget}>
          ${r.map(n=>l`<option value=${n.id} ?selected=${n.id===i}>
                ${Te(n,this.locale)}
              </option>`)}
        </select>
      </label>`}_renderSplit(){let e=this._details?.origins??[],r=this.locale;return l`<fieldset aria-describedby="split-hint">
        <legend>${s.splitIntro}</legend>
        ${e.map((i,n)=>{let o=i.time?j(i.time,r):"";return l`<label class="check-row">
            <input
              type="checkbox"
              .value=${i.id}
              .checked=${T(this._splitSelection.includes(i.id))}
              ?data-first=${n===0}
              @change=${this._onSplitChange}
            />
            <span>
              ${i.label.trim()||St(i.source)}${o?l`<span class="muted"> · ${o}</span>`:c}
            </span>
          </label>`})}
      </fieldset>
      <p class="hint" id="split-hint">${s.splitHint}</p>`}_renderActions(e){let r=this._busy?"true":"false",i=l`<button type="button" class="btn" data-cancel @click=${this._backToView}>
      ${s.cancel}
    </button>`;switch(this._mode){case"date":return l`<div class="dialog-actions">
          ${i}
          <button type="submit" form="date-form" class="btn primary" aria-disabled=${r}>
            ${s.save}
          </button>
        </div>`;case"merge":{let n=et(this.snapshot?.parcels??[],e.id);return l`<div class="dialog-actions">
          ${i}
          ${n.length?l`<button
                type="button"
                class="btn primary"
                aria-disabled=${r}
                @click=${this._merge}
              >
                ${s.mergeConfirm}
              </button>`:c}
        </div>`}case"split":{let n=yt(this._splitSelection,this._details?.origins.length??0);return l`<div class="dialog-actions">
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
        </div>`;default:{let n=(this._details?.origins.length??0)>=2;return l`<div class="dialog-actions" role="group" aria-label=${s.actions}>
          <button type="button" class="btn" data-mode="date" @click=${this._editDate}>
            ${s.editDate}
          </button>
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
          ${Xe(e.status)?l`<span class="spacer"></span>
                <button
                  type="button"
                  class="btn primary"
                  aria-disabled=${r}
                  @click=${this._markDelivered}
                >
                  <ha-icon icon="mdi:check" aria-hidden="true"></ha-icon>${s.markDelivered}
                </button>`:c}
        </div>`}}}_setMode(e){this._mode=e,this._error=null,this._formError=null,this.focusAfterRender(e==="archive"?"[data-cancel]":"[data-first], [data-cancel]")}_backToView(){let e=this._mode;this._mode="view",this._error=null,this._formError=null,this.focusAfterRender(`[data-mode="${e}"]`)}_editDate(){let e=this._parcel;this._dateForm=e?Tr(e):Zr,this._setMode("date")}_startMerge(){this._mergeTarget="",this._setMode("merge")}_startSplit(){this._splitSelection=[],this._setMode("split")}_startArchive(){this._setMode("archive")}_parcelService(e,r,i){let n=this.hass,o=this._parcel;!n||!o||this.runAction(()=>Y(n,e,{parcel_id:o.id,...r}),i)}_confirm(){this._parcelService("update",{confirm:!0})}_undoMerge(){this._parcelService("undo_merge",{})}_keepMerge(){this._parcelService("update",{confirm_merge:!0})}_undoInferred(){this._parcelService("undo_delivery",{})}_keepInferred(){this._parcelService("update",{confirm_delivery:!0})}_markDelivered(){this._parcelService("mark_delivered",{})}_archive(){this._parcelService("archive",{},()=>this.closeDialog())}_onPrivateClick(e){this._busy&&e.preventDefault()}_togglePrivate(e){let r=e.currentTarget.checked,i=this.hass,n=this._parcel;!i||!n||this._busy||(this._pendingPrivate=r,this.runAction(async()=>{try{await Y(i,"update",{parcel_id:n.id,private:r})}catch(o){throw this._pendingPrivate=null,o}}))}_onDateInput(e){let r=e.currentTarget,i=r.name;this._dateForm={...this._dateForm,[i]:r.value},this._formError=null}_saveDate(e){e.preventDefault();let r=this._parcel;if(!r||this._busy)return;let i=this._dateForm,n=Ke(i);if(n){this._formError=n,this.focusAfterRender(`[name="${n.field}"]`);return}let o=Er(r.id,i);this._parcelService("update",o,()=>this._backToView())}_resolvedMergeTarget(e){return e.some(r=>r.id===this._mergeTarget)?this._mergeTarget:e[0]?.id??""}_onMergeTarget(e){this._mergeTarget=e.currentTarget.value}_merge(){let e=this.hass,r=this._parcel;if(!e||!r)return;let i=this._resolvedMergeTarget(et(this.snapshot?.parcels??[],r.id));i&&this.runAction(()=>Y(e,"merge",{parcel_ids:[r.id,i]}),()=>this._backToView())}_onSplitChange(e){let r=e.currentTarget,i=this._splitSelection.filter(n=>n!==r.value);this._splitSelection=r.checked?[...i,r.value]:i}_split(){let e=this._details?.origins.length??0;yt(this._splitSelection,e)&&this._parcelService("split",{origins:[...this._splitSelection]},()=>this._backToView())}async _copy(e){let r=e.currentTarget,i=this._parcel?.tracking_number?.trim();if(!i)return;this._copyState="idle";try{if(!navigator.clipboard?.writeText)throw new Error("Clipboard API unavailable");await navigator.clipboard.writeText(i),this._copyState="copied";return}catch{}let n=this.renderRoot.querySelector("#tracking-number");n?.focus(),n?.select();let o=!1;try{o=document.execCommand("copy")}catch{o=!1}this._copyState=o?"copied":"failed",o&&r.focus()}};I("parcels-details-dialog",Ct);var nn="parcels/subscribe",Jr=[2e3,1e4,3e4,6e4,3e5],it=new Map,sn=0;function Xr(t,e){try{t(e)}catch(r){console.error(r)}}function Qr(t,e){t.state=e;for(let r of[...t.listeners.values()])Xr(r,e)}function ei(t){try{t().catch(()=>{})}catch{}}function st(t){t.retryTimer!==void 0&&(clearTimeout(t.retryTimer),t.retryTimer=void 0)}function nt(t){t.connection.removeEventListener("ready",t.onReady),t.connection.removeEventListener("disconnected",t.onDisconnected)}function on(t){st(t);let e=Jr[Math.min(t.retries,Jr.length-1)]??3e5;t.retries+=1,t.retryTimer=setTimeout(()=>{t.retryTimer=void 0,At(t)},e)}function At(t){if(t.released||t.unsubscribe||t.pending||t.listeners.size===0)return;st(t);let e=++t.attempt,r=t.epoch,i=()=>!t.released&&t.attempt===e;t.pending=!0;let n;try{n=t.connection.subscribeMessage(o=>{i()&&(t.retries=0,Qr(t,{snapshot:Yr(o),error:null}))},{type:nn},{resubscribe:!1})}catch(o){n=Promise.reject(o)}n.then(o=>{if(i()){t.pending=!1,t.unsubscribe=o;return}t.epoch===r&&ei(o),t.released&&t.attempt===e+1&&(t.pending=!1,nt(t))},o=>{i()?(t.pending=!1,Qr(t,{snapshot:t.state.snapshot,error:R(o)}),on(t)):t.released&&t.attempt===e+1&&(t.pending=!1,nt(t))})}function an(t,e){if(!t.listeners.delete(e)||t.listeners.size>0)return;t.released=!0,t.attempt+=1,st(t),it.get(t.connection)===t&&it.delete(t.connection);let r=t.unsubscribe;t.unsubscribe=null,r&&ei(r),t.pending||nt(t)}function ln(t){let e={connection:t,listeners:new Map,state:{snapshot:null,error:null},epoch:0,attempt:0,unsubscribe:null,pending:!1,released:!1,retries:0,retryTimer:void 0,onReady:()=>{e.released||e.unsubscribe||(e.pending=!1,e.retries=0,At(e))},onDisconnected:()=>{e.epoch+=1,e.attempt+=1,e.unsubscribe=null,e.pending=!1,st(e),e.released&&nt(e)}};return e}function ti(t,e){let r=++sn,i=it.get(t);i?(i.listeners.set(r,e),(i.state.snapshot||i.state.error)&&Xr(e,i.state)):(i=ln(t),it.set(t,i),i.listeners.set(r,e),t.addEventListener("ready",i.onReady),t.addEventListener("disconnected",i.onDisconnected),At(i));let n=i,o=!0;return()=>{o&&(o=!1,an(n,r))}}var ot=class{snapshot=null;error=null;_host;_connection=null;_unsubscribe=null;_hostConnected=!1;constructor(e){this._host=e,e.addController(this)}setConnection(e){e!==this._connection&&(this._release(),this._connection=e,this.snapshot=null,this.error=null,this._hostConnected&&this._subscribe(),this._host.requestUpdate())}hostConnected(){this._hostConnected=!0,this._subscribe()}hostDisconnected(){this._hostConnected=!1,this._release()}_subscribe(){!this._connection||this._unsubscribe||(this._unsubscribe=ti(this._connection,e=>{this.snapshot=e.snapshot??this.snapshot,this.error=e.error,this._host.requestUpdate()}))}_release(){let e=this._unsubscribe;this._unsubscribe=null,e?.()}};var Ee=class extends E{static properties={_actionError:{state:!0}};_snapshots=new ot(this);_hass=void 0;_hassKey=null;_locale=null;_localeKey="";constructor(){super(),this._actionError=null}get hass(){return this._hass}set hass(e){this._hass=e,this._snapshots.setConnection(e?.connection??null),this.toggleAttribute("dark",e?.themes?.darkMode===!0);let r=JSON.stringify([e?.language,e?.locale?.language,e?.locale?.time_format,e?.locale?.time_zone,e?.config?.time_zone,e?.user?.is_admin,e?.themes?.darkMode]);r!==this._hassKey&&(this._hassKey=r,this.requestUpdate()),this.hassChanged()}hassChanged(){}get snapshot(){return this._snapshots.snapshot}get locale(){let e=this._snapshots.snapshot?.settings.time_zone,r=`${this._hassKey??""}|${e??""}`;return(!this._locale||r!==this._localeKey)&&(this._locale=Ge(this._hass,e),this._localeKey=r),this._locale}async callService(e,r,i){let n=this._hass;if(!n)return!1;this._actionError=null;try{return await Y(n,e,r),!0}catch(o){return this._actionError=f(i,{message:R(o)}),!1}}renderBanners(){let{snapshot:e,error:r}=this._snapshots;return!r&&!this._actionError?c:l`<div class="banners">
      ${r?l`<div class="alert ${e?"warning":"error"}" role="alert">
            <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              ${f(e?s.refreshError:s.loadError,{message:r})}
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
    </div>`}renderLoading(){return this._snapshots.error?c:l`<p class="empty" role="status">${s.loading}</p>`}showActionError(e){this._actionError=e}_dismissActionError(){this._actionError=null}},ue=class extends Ee{static properties={_busyParcels:{state:!0}};_focusedParcel=null;constructor(){super(),this._busyParcels=new Set}willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement;this._focusedParcel=r instanceof HTMLElement?r.closest(".chip[data-parcel-id]")?.dataset.parcelId??null:null}updated(e){super.updated(e);let r=this._focusedParcel;this._focusedParcel=null,r!==null&&!this.shadowRoot?.activeElement&&Rt()&&this.renderRoot.querySelector(Tt(r))?.focus()}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback], button.chip-main")}openDetails=(e,r)=>{this.renderRoot.querySelector("parcels-details-dialog")?.open(e.id,()=>{(r.isConnected?r:this.renderRoot.querySelector(Tt(e.id))??this.focusFallback())?.focus()})};undoMerge=e=>{this._parcelAction(e.id,"undo_merge",{parcel_id:e.id},s.undoFailed)};keepMerge=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_merge:!0},s.keepFailed)};undoInferred=e=>{this._parcelAction(e.id,"undo_delivery",{parcel_id:e.id},s.undoInferredFailed)};keepInferred=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_delivery:!0},s.keepInferredFailed)};renderDetailsDialog(){return l`<parcels-details-dialog
      .hass=${this.hass}
      .snapshot=${this.snapshot}
      .locale=${this.locale}
      @parcels-error=${this._onDialogError}
    ></parcels-details-dialog>`}async _parcelAction(e,r,i,n){if(!this._busyParcels.has(e)){this._busyParcels=new Set([...this._busyParcels,e]);try{await this.callService(r,i,n)}finally{let o=new Set(this._busyParcels);o.delete(e),this._busyParcels=o}}}_onDialogError(e){this.showActionError(e.detail)}};function Rt(){let t=document.activeElement;return!t||t===document.body}function Pt(t){if(typeof t!="object"||t===null||Array.isArray(t))throw new Error(s.configInvalid);return t}function Mt(t){let e=t.title;if(e!=null){if(typeof e!="string")throw new Error(s.configTitle);return e.trim()}}function Lt(t){return typeof t.type=="string"?t.type:""}function Dt(t){let e=Pt(t),r=e.show_archived??!0;if(typeof r!="boolean")throw new Error(s.configShowArchived);return{type:Lt(e),title:Mt(e),show_archived:r}}function It(t){let e=Pt(t);return{type:Lt(e),title:Mt(e)}}function Ot(t){let e=Pt(t);return{type:Lt(e),title:Mt(e)}}function he(t,e){return t===void 0?e:t||null}function dn(t,e){let r=$e(t.status_time,e.timeZone);switch(t.status){case"cancelled":return null;case"delivered":{let n=$e(t.delivered_at,e.timeZone)??r;return n?{kind:"delivered",from:n,to:n}:null}case"returned":return r?{kind:"returned",from:r,to:r}:null;case"ready_for_pickup":{let n=r??e.today;return{kind:"pickup",from:n,to:kr(n,e.today)}}default:break}let i=W(t);return i?{kind:"eta",from:i.start,to:i.end}:(t.status==="attempted"||t.status==="exception")&&r?{kind:"status",from:r,to:r}:null}function ri(t){return t.window_start??t.window_end??"~"}function Nt(t,e){return t<e?-1:t>e?1:0}function cn(t,e){return t.startCol-e.startCol||e.endCol-e.startCol-(t.endCol-t.startCol)||Nt(ri(t.parcel),ri(e.parcel))||Nt(x(t.parcel).toLowerCase(),x(e.parcel).toLowerCase())||Nt(t.parcel.id,e.parcel.id)}function ii(t,e,r,i){let n=xr(e),o=le(e,6),a=[];for(let u of t){if(u.archived&&!i.showArchived)continue;let m=dn(u,r);!m||P(m.to,e)<0||P(m.from,o)>0||a.push({parcel:u,placement:m,startCol:Math.max(0,_t(e,m.from)),endCol:Math.min(6,_t(e,m.to)),continuesBefore:P(m.from,e)<0,continuesAfter:P(m.to,o)>0,lane:0})}a.sort(cn);let p=[];for(let u of a){let m=p.findIndex(h=>h<u.startCol);m===-1&&(m=p.length),p[m]=u.endCol,u.lane=m}let d=n.map((u,m)=>a.filter(h=>h.startCol<=m&&m<=h.endCol).sort((h,g)=>h.lane-g.lane));return{start:e,end:o,days:n,items:a,lanes:p.length,perDay:d,busy:d.map(u=>u.length>0)}}var pn=600,un=616,hn={weekday:"short"},mn={day:"numeric"},fn={weekday:"long",day:"numeric",month:"long"},gn={weekday:"long",day:"numeric",month:"short"},Ft=class extends ue{static properties={_config:{state:!0},_weekOffset:{state:!0},_narrow:{state:!0},_refreshing:{state:!0}};static styles=[O,Ve,w`
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
    `];_resizeObserver=null;_resizeFrame=0;_layoutCache=null;constructor(){super(),this._config=Dt({}),this._weekOffset=0,this._narrow=!1,this._refreshing=!1}static getStubConfig(){return{}}setConfig(e){this._config=Dt(e)}getCardSize(){let e=this._layout();return e?this._narrow?9+e.perDay.reduce((i,n)=>i+n.length,0):3+Math.max(1,e.lanes):4}getGridOptions(){return{columns:"full",rows:"auto",min_columns:6}}connectedCallback(){super.connectedCallback(),typeof ResizeObserver<"u"&&(this._resizeObserver??=new ResizeObserver(e=>{let r=e[e.length-1]?.contentRect.width??0;cancelAnimationFrame(this._resizeFrame),this._resizeFrame=requestAnimationFrame(()=>this._measure(r))}),this._resizeObserver.observe(this))}disconnectedCallback(){super.disconnectedCallback(),this._resizeObserver?.disconnect(),cancelAnimationFrame(this._resizeFrame)}firstUpdated(e){super.firstUpdated(e),this._measure(this.getBoundingClientRect().width)}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback]")}_measure(e){e<=0||(e<pn?this._narrow=!0:e>=un&&(this._narrow=!1))}_monday(e){return le(wr(e.settings.today),7*this._weekOffset)}_layout(){let e=this.snapshot;if(!e)return null;let r=this._monday(e),i=this._config.show_archived,n=this._layoutCache;if(n&&n.snapshot===e&&n.monday===r&&n.showArchived===i)return n.layout;let o=ii(e.parcels,r,{today:e.settings.today,timeZone:e.settings.time_zone},{showArchived:i});return this._layoutCache={snapshot:e,monday:r,showArchived:i,layout:o},o}render(){let e=this.snapshot,r=this._layout(),i=he(this._config.title,s.defaultWeekTitle),n=r?N(r.start,r.end,this.locale,Dr):"";return l`<ha-card>
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
        ${this.renderBanners()}
        ${e&&r?this._narrow?this._renderStacked(e,r,n):this._renderGrid(e,r,n):l`<div class="content">${this.renderLoading()}</div>`}
      </ha-card>
      ${this.renderDetailsDialog()}
      <parcels-add-dialog
        .hass=${this.hass}
        @parcels-error=${this._onAddError}
      ></parcels-add-dialog>`}_renderGrid(e,r,i){let n=this.locale,o=e.settings.today,a=r.items.length===0,d={"grid-template-columns":r.busy.map(u=>u||a?"minmax(0, 1fr)":"minmax(0, 0.6fr)").join(" "),"grid-template-rows":`auto repeat(${Math.max(1,r.lanes)}, auto)`};return l`<div
      class="grid"
      role="group"
      aria-label=${f(s.weekOf,{range:i})}
      style=${A(d)}
    >
      ${r.days.map((u,m)=>l`<div
            class="day-bg ${u===o?"today":""}"
            style=${A({"grid-column":String(m+1)})}
            aria-hidden="true"
          ></div>`)}
      ${r.days.map((u,m)=>l`<div
            class="day-head ${u===o?"today":""}"
            style=${A({"grid-column":String(m+1)})}
            aria-current=${u===o?"date":c}
          >
            <span class="dow" aria-hidden="true">${ie(u,n,hn)}</span>
            <span class="dom" aria-hidden="true">${ie(u,n,mn)}</span>
            <span class="sr-only">${ie(u,n,fn)}</span>
          </div>`)}
      ${a?l`<p class="week-empty">${s.noDeliveriesThisWeek}</p>`:c}
      ${B(r.items,u=>u.parcel.id,u=>this._chip(u,!1,{"grid-column":`${u.startCol+1} / ${u.endCol+2}`,"grid-row":String(u.lane+2)}))}
    </div>`}_renderStacked(e,r,i){let n=this.locale,o=e.settings.today;return l`<ol class="days" aria-label=${f(s.weekOf,{range:i})}>
      ${r.days.map((a,p)=>{let d=r.perDay[p]??[],u=a===o;return l`<li
          class="day ${d.length?"":"compact"} ${u?"today":""}"
          aria-current=${u?"date":c}
        >
          <p class="day-label">
            ${ie(a,n,gn)}${u?l`<span class="badge info">${s.todayTag}</span>`:c}
          </p>
          ${d.length?l`<ul class="day-chips">
                ${B(d,m=>m.parcel.id,m=>l`<li>${this._chip(m,!0,void 0,p)}</li>`)}
              </ul>`:l`<span class="muted">${s.noDeliveriesThisDay}</span>`}
        </li>`})}
    </ol>`}_chip(e,r,i,n){let o=e.continuesBefore&&(!r||n===e.startCol),a=e.continuesAfter&&(!r||n===e.endCol);return tt(e.parcel,{locale:this.locale,placement:e.placement,continuesBefore:o,continuesAfter:a,showRange:r,busy:this._busyParcels.has(e.parcel.id),position:i,onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge,onUndoInferred:this.undoInferred,onKeepInferred:this.keepInferred})}_previousWeek(){this._weekOffset-=1}_nextWeek(){this._weekOffset+=1}_thisWeek(){this._weekOffset=0}async _refresh(){if(!this._refreshing){this._refreshing=!0;try{await this.callService("refresh",{},s.refreshFailed)}finally{this._refreshing=!1}}}_openAdd(e){let r=e.currentTarget;this.renderRoot.querySelector("parcels-add-dialog")?.open(()=>{r.isConnected&&r.focus()})}_onAddError(e){this.showActionError(e.detail)}};I("parcels-week-card",Ft);de("parcels-week-card",s.weekCardName,s.weekCardDescription);var Ht=class extends ue{static properties={_config:{state:!0}};static styles=[O,Ve,w`
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
    `];_listCache=null;constructor(){super(),this._config=It({})}static getStubConfig(){return{}}setConfig(e){this._config=It(e)}getCardSize(){let e=this._parcels();return e?1+Math.max(1,e.length):3}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}focusFallback(){return this.renderRoot.querySelector("button.chip-main")??this.renderRoot.querySelector(".content")}_parcels(){let e=this.snapshot;return e?(this._listCache?.snapshot!==e&&(this._listCache={snapshot:e,parcels:zr(e.parcels)}),this._listCache.parcels):null}render(){let e=this._parcels(),r=he(this._config.title,s.defaultListTitle);return l`<ha-card>
        ${r?l`<div class="header"><h2 class="title">${r}</h2></div>`:c}
        ${this.renderBanners()}
        <div class="content" tabindex="-1">
          ${e?this._renderList(e):this.renderLoading()}
        </div>
      </ha-card>
      ${this.renderDetailsDialog()}`}_renderList(e){if(!e.length)return l`<p class="empty">${s.noUndatedParcels}</p>`;let r=this.locale;return l`<ul class="list">
      ${B(e,i=>i.id,i=>l`<li>
            ${tt(i,{locale:r,showStatus:!0,busy:this._busyParcels.has(i.id),onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge,onUndoInferred:this.undoInferred,onKeepInferred:this.keepInferred})}
          </li>`)}
    </ul>`}};I("parcels-list-card",Ht);de("parcels-list-card",s.listCardName,s.listCardDescription);var me=["review","filtered"],bn=new Set(["not_parcel","unknown"]),_n={weekday:"short",day:"numeric",month:"short"};function ni(t){return M(t.received??t.created)??-1/0}function si(t){return[...t].sort((e,r)=>ni(r)-ni(e)||(e.id<r.id?-1:e.id>r.id?1:0))}function vn(t){return[...t].sort((e,r)=>(r.day??"").localeCompare(e.day??"")||(e.id<r.id?-1:e.id>r.id?1:0))}function Ut(t,e){if(!t.has(e))return t;let r=new Map(t);return r.delete(e),r}var Bt=class extends Ee{static properties={_config:{state:!0},_tab:{state:!0},_editing:{state:!0},_editForm:{state:!0},_editProblem:{state:!0},_busyItems:{state:!0},_itemErrors:{state:!0}};static styles=[O,w`
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
      .filtered-hint {
        margin-bottom: 12px;
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
    `];connectedWhileHidden=!0;_focusedItem=null;_listCache=null;constructor(){super(),this._config=Ot({}),this._tab="review",this._editing=null,this._editForm=vt(null),this._editProblem=null,this._busyItems=new Set,this._itemErrors=new Map}static getStubConfig(){return{}}setConfig(e){this._config=Ot(e)}getCardSize(){if(!this._visible())return 0;let e=this._lists();if(!e)return 3;let r=this._tab==="review"?e.review.length+e.suggestions.length:e.filtered.length;return 2+2*Math.max(1,r)}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}hassChanged(){this._syncVisibility()}_visible(){let e=this.snapshot;return e?e.settings.user_is_admin:this.hass?.user?.is_admin===!0}_syncVisibility(){let e=!this._visible();this.hidden!==e&&(this.hidden=e,this.dispatchEvent(new CustomEvent("card-visibility-changed",{bubbles:!0,composed:!0,detail:{value:!e}})))}_lists(){let e=this.snapshot;return e?(this._listCache?.snapshot!==e&&(this._listCache={snapshot:e,review:si(e.review),suggestions:vn(e.merge_suggestions),filtered:si(e.filtered)}),this._listCache):null}_listed(e){let r=this._lists();return r?[...r.review,...r.suggestions,...r.filtered].some(i=>i.id===e):!1}willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement,i=r instanceof HTMLElement?r.closest("[data-item-id]"):null;if(i){let o=[...this.renderRoot.querySelectorAll("[data-item-id]")].filter(a=>!a.closest("[hidden]"));this._focusedItem={id:i.dataset.itemId??"",index:o.indexOf(i)}}else this._focusedItem=null;let n=this._lists();if(n){let o=new Set([...n.review,...n.suggestions,...n.filtered].map(a=>a.id));this._editing!==null&&!o.has(this._editing)&&(this._editing=null,this._editProblem=null);for(let a of this._itemErrors.keys())o.has(a)||(this._itemErrors=Ut(this._itemErrors,a))}}updated(e){super.updated(e),this._syncVisibility();let r=this._focusedItem;if(this._focusedItem=null,!r||this.shadowRoot?.activeElement||!Rt())return;let n=[...this.renderRoot.querySelector(`#panel-${this._tab}`)?.querySelectorAll("[data-item-id]")??[]];(n.find(a=>a.dataset.itemId===r.id)??n[Math.min(Math.max(r.index,0),n.length-1)]??this.renderRoot.querySelector(`#tab-${this._tab}`))?.focus()}render(){if(!this._visible())return c;let e=this._lists(),r=he(this._config.title,s.defaultReviewTitle);return l`<ha-card>
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
    </ha-card>`}_renderTabs(e,r){let i=n=>f(s.tabCount,{label:n==="review"?s.tabReview:s.tabFiltered,count:n==="review"?e:r});return l`<div
      class="tabs"
      role="tablist"
      aria-label=${s.reviewTabs}
      @keydown=${this._onTabKeyDown}
    >
      ${me.map(n=>{let o=this._tab===n;return l`<button
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
    </div>`}_renderReviewList(e,r){return!e.length&&!r.length?l`<p class="empty">${s.emptyReview}</p>`:l`<div class="items">
      ${B(r,i=>i.id,(i,n)=>this._renderMergeSuggestion(i,n))}
      ${B(e,i=>i.id,(i,n)=>this._renderReviewItem(i,n))}
    </div>`}_renderMergeSuggestion(e,r){let i=this.locale,o=this._busyItems.has(e.id)?"true":"false",a=`suggestion-subject-${r}`,p=x(e.parcel),d=Je(e.reason);return l`<article
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
        ${f(s.suggestionTitle,{parcel:Te(e.parcel,i)})}
      </h3>
      ${d?l`<p class="meta">${f(s.reasonIs,{reason:d})}</p>`:c}
      <p class="hint">${s.suggestionHint}</p>
      <ul class="candidates">
        ${e.candidates.map(u=>{let m=Te(u,i),h=[u.order_numbers.join(", "),u.items.join(", ")].filter(Boolean).join(" \xB7 ");return l`<li class="candidate">
            <span class="grow">
              <span class="block">${m}</span>
              ${h?l`<span class="meta block">${h}</span>`:c}
            </span>
            <button
              type="button"
              class="btn"
              aria-label=${f(s.mergeSuggestedLabel,{candidate:m,title:p})}
              aria-disabled=${o}
              @click=${()=>this._command(e.id,"suggestion/accept",{suggestion_id:e.id,parcel_id:u.id})}
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
          aria-label=${f(s.keepApartLabel,{title:p})}
          aria-disabled=${o}
          @click=${()=>this._command(e.id,"suggestion/dismiss",{suggestion_id:e.id})}
        >
          ${s.keepApart}
        </button>
      </div>
    </article>`}_renderFilteredList(e){return l`<p class="hint filtered-hint">${s.filteredHint}</p>
      ${e.length?l`<div class="items">
            ${B(e,r=>r.id,(r,i)=>this._renderFilteredItem(r,i))}
          </div>`:l`<p class="empty">${s.emptyFiltered}</p>`}`}_renderHead(e,r,i=c){return l`<div class="item-head">
        <span class="sender">${e.sender||e.sender_domain}</span>${i}
      </div>
      <h3 class="subject" id=${r}>${e.subject.trim()||s.noSubject}</h3>`}_renderError(e){let r=this._itemErrors.get(e);return r?l`<div class="alert error" role="alert">
          <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
          <span class="grow">${r}</span>
        </div>`:c}_renderReviewItem(e,r){let i=this.locale,n=this._busyItems.has(e.id),o=this._editing===e.id,a=`review-subject-${r}`,p=e.received??e.created,d=Or(e.reason),u=[p?f(s.receivedOn,{date:j(p,i)}):"",e.mailbox_owner?f(s.mailboxOf,{owner:e.mailbox_owner}):"",d?f(s.reasonIs,{reason:d}):""].filter(Boolean),m=e.source==="ai"?l`<span class="badge ai" title=${s.aiSuggestionLabel}>
            ${s.aiBadge}<span class="sr-only">, ${s.aiSuggestionLabel}</span>
          </span>`:c;return l`<article
      class="item"
      tabindex="-1"
      data-item-id=${e.id}
      aria-labelledby=${a}
      aria-busy=${n?"true":"false"}
    >
      ${this._renderHead(e,a,m)}
      ${u.length?l`<p class="meta">${u.join(" \xB7 ")}</p>`:c}
      ${e.authenticated?c:l`<div class="alert warning">
            <ha-icon icon="mdi:shield-alert-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              <strong class="block">${s.unverifiedSender}</strong>
              ${s.unverifiedSenderHint}
            </span>
          </div>`}
      ${o?this._renderEditForm(e,n):this._renderSuggestion(e.suggestion)}
      ${this._renderError(e.id)} ${o?c:this._renderReviewActions(e,n)}
    </article>`}_renderSuggestion(e){if(!e)return l`<p class="hint section-label">${s.noSuggestion}</p>`;let r=this.locale,i=W(e),n=[[s.fieldKind,kt(e.kind)||null],[s.fieldMerchant,e.merchant],[s.fieldCarrier,pe({carrier:e.carrier,carrier_name:null})],[s.fieldTrackingNumbers,e.tracking_numbers.join(", ")||null],[s.fieldOrderNumbers,e.order_numbers.join(", ")||null],[s.expected,i?N(i.start,i.end,r,_n):null],[s.timeWindow,ce(e.window_start,e.window_end,r)],[s.pickupPoint,e.pickup_point],[s.pickupCode,e.pickup_code],[s.items,e.items.length?l`<ul>
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
      <button
        type="button"
        class="btn"
        title=${f(s.trustSenderHint,{domain:n})}
        aria-disabled=${i}
        @click=${()=>this._command(e.id,"review/trust_sender",{review_id:e.id})}
      >
        ${s.trustSender}
      </button>
      <button
        type="button"
        class="btn danger"
        title=${f(s.ignoreSenderHint,{domain:n})}
        aria-disabled=${i}
        @click=${()=>this._command(e.id,"review/ignore_sender",{review_id:e.id})}
      >
        ${s.ignoreSender}
      </button>
    </div>`}_renderEditForm(e,r){let i=this._editForm,n=this._editProblem,o=Object.keys(Be).filter(d=>!bn.has(d)||d===i.kind);o.includes(i.kind)||o.unshift(i.kind);let a=Ue();i.carrier&&!Object.hasOwn(q,i.carrier)&&a.unshift({id:i.carrier,name:i.carrier});let p=(d,u,m="text",h)=>{let g=n?.field===d,b=[g?"edit-error":"",h??""].filter(Boolean).join(" ");return l`<label class="field">
        <span class="field-label">${u}</span>
        <input
          type=${m}
          name=${d}
          autocomplete="off"
          .value=${T(i[d])}
          aria-invalid=${g?"true":"false"}
          aria-describedby=${b||c}
          @input=${this._onEditInput}
        />
      </label>`};return l`<form id="edit-form" class="edit-form" novalidate @submit=${this._submitEdit}>
      <div class="form-grid">
        <label class="field">
          <span class="field-label">${s.fieldKind}</span>
          <select name="kind" data-first @change=${this._onEditInput}>
            ${o.map(d=>l`<option value=${d} ?selected=${d===i.kind}>
                  ${kt(d)||d}
                </option>`)}
          </select>
        </label>
        ${p("merchant",s.fieldMerchant)}
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
          ${p("tracking_numbers",s.fieldTrackingNumbers,"text","edit-hint-tracking")}
          <p class="hint" id="edit-hint-tracking">${s.hintList}</p>
        </div>
        <div class="field">
          ${p("order_numbers",s.fieldOrderNumbers,"text","edit-hint-orders")}
          <p class="hint" id="edit-hint-orders">${s.hintList}</p>
        </div>
        ${p("eta_start",s.fieldEtaStart,"date")}
        ${p("eta_end",s.fieldEtaEnd,"date")}
        ${p("window_start",s.fieldWindowStart,"time")}
        ${p("window_end",s.fieldWindowEnd,"time")}
        ${p("pickup_point",s.fieldPickupPoint)}
        ${p("pickup_code",s.fieldPickupCode)}
        <label class="field wide">
          <span class="field-label">${s.fieldItems}</span>
          <textarea
            name="items"
            rows="3"
            .value=${T(i.items)}
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
            ${f(s.receivedOn,{date:j(n,this.locale)})}
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
      </div>
    </article>`}_selectTab(e,r){this._tab=e,r&&this.updateComplete.then(()=>this.renderRoot.querySelector(`#tab-${e}`)?.focus())}_onTabClick(e){let r=e.currentTarget.dataset.tab;this._selectTab(r,!1)}_onTabKeyDown(e){let r=me.indexOf(this._tab),i=getComputedStyle(e.currentTarget).direction==="rtl",n;switch(e.key){case"ArrowRight":n=r+(i?-1:1);break;case"ArrowLeft":n=r+(i?1:-1);break;case"Home":n=0;break;case"End":n=me.length-1;break;default:return}e.preventDefault();let o=me[(n+me.length)%me.length];o&&this._selectTab(o,!0)}_focusInItem(e,r){this.updateComplete.then(()=>{let i=this.renderRoot.querySelector(`[data-item-id="${CSS.escape(e)}"]`);(i?.querySelector(r)??i)?.focus()})}_startEdit(e){this._busyItems.has(e.id)||(this._editing=e.id,this._editForm=vt(e.suggestion),this._editProblem=null,this._itemErrors=Ut(this._itemErrors,e.id),this._focusInItem(e.id,"[data-first]"))}_cancelEdit(e){this._editing=null,this._editProblem=null,this._focusInItem(e,"[data-edit]")}_onEditInput(e){let r=e.currentTarget,i=r.name;this._editForm={...this._editForm,[i]:r.value},this._editProblem=null}_submitEdit(e){e.preventDefault();let r=this._editing;if(r===null||this._busyItems.has(r))return;let i=Ke(this._editForm);if(i){this._editProblem=i,this._focusInItem(r,`[name="${i.field}"]`);return}this._command(r,"review/accept",{review_id:r,overrides:Ar(this._editForm)},()=>{this._editing===r&&(this._editing=null)})}_accept(e){this._command(e.id,"review/accept",{review_id:e.id})}async _command(e,r,i,n){let o=this.hass;if(!(!o||this._busyItems.has(e))){this._busyItems=new Set([...this._busyItems,e]),this._itemErrors=Ut(this._itemErrors,e);try{await He(o,r,i),n?.()}catch(a){let p=f(s.actionFailed,{message:R(a)});this._listed(e)?this._itemErrors=new Map([...this._itemErrors,[e,p]]):this.showActionError(p)}finally{let a=new Set(this._busyItems);a.delete(e),this._busyItems=a}}}};I("parcels-review-card",Bt);de("parcels-review-card",s.reviewCardName,s.reviewCardDescription);
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
