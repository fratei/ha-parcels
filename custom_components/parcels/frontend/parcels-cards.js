var Ee=globalThis,Ce=Ee.ShadowRoot&&(Ee.ShadyCSS===void 0||Ee.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,st=Symbol(),Ut=new WeakMap,fe=class{constructor(e,r,i){if(this._$cssResult$=!0,i!==st)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=r}get styleSheet(){let e=this.o,r=this.t;if(Ce&&e===void 0){let i=r!==void 0&&r.length===1;i&&(e=Ut.get(r)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&Ut.set(r,e))}return e}toString(){return this.cssText}},Bt=t=>new fe(typeof t=="string"?t:t+"",void 0,st),w=(t,...e)=>{let r=t.length===1?t[0]:e.reduce((i,n,s)=>i+(a=>{if(a._$cssResult$===!0)return a.cssText;if(typeof a=="number")return a;throw Error("Value passed to 'css' function must be a 'css' function result: "+a+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(n)+t[s+1],t[0]);return new fe(r,t,st)},zt=(t,e)=>{if(Ce)t.adoptedStyleSheets=e.map(r=>r instanceof CSSStyleSheet?r:r.styleSheet);else for(let r of e){let i=document.createElement("style"),n=Ee.litNonce;n!==void 0&&i.setAttribute("nonce",n),i.textContent=r.cssText,t.appendChild(i)}},ot=Ce?t=>t:t=>t instanceof CSSStyleSheet?(e=>{let r="";for(let i of e.cssRules)r+=i.cssText;return Bt(r)})(t):t;var{is:si,defineProperty:oi,getOwnPropertyDescriptor:ai,getOwnPropertyNames:li,getOwnPropertySymbols:di,getPrototypeOf:ci}=Object,Ae=globalThis,Wt=Ae.trustedTypes,pi=Wt?Wt.emptyScript:"",ui=Ae.reactiveElementPolyfillSupport,ge=(t,e)=>t,at={toAttribute(t,e){switch(e){case Boolean:t=t?pi:null;break;case Object:case Array:t=t==null?t:JSON.stringify(t)}return t},fromAttribute(t,e){let r=t;switch(e){case Boolean:r=t!==null;break;case Number:r=t===null?null:Number(t);break;case Object:case Array:try{r=JSON.parse(t)}catch{r=null}}return r}},Kt=(t,e)=>!si(t,e),jt={attribute:!0,type:String,converter:at,reflect:!1,useDefault:!1,hasChanged:Kt};Symbol.metadata??=Symbol("metadata"),Ae.litPropertyMetadata??=new WeakMap;var H=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,r=jt){if(r.state&&(r.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((r=Object.create(r)).wrapped=!0),this.elementProperties.set(e,r),!r.noAccessor){let i=Symbol(),n=this.getPropertyDescriptor(e,i,r);n!==void 0&&oi(this.prototype,e,n)}}static getPropertyDescriptor(e,r,i){let{get:n,set:s}=ai(this.prototype,e)??{get(){return this[r]},set(a){this[r]=a}};return{get:n,set(a){let p=n?.call(this);s?.call(this,a),this.requestUpdate(e,p,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??jt}static _$Ei(){if(this.hasOwnProperty(ge("elementProperties")))return;let e=ci(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(ge("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(ge("properties"))){let r=this.properties,i=[...li(r),...di(r)];for(let n of i)this.createProperty(n,r[n])}let e=this[Symbol.metadata];if(e!==null){let r=litPropertyMetadata.get(e);if(r!==void 0)for(let[i,n]of r)this.elementProperties.set(i,n)}this._$Eh=new Map;for(let[r,i]of this.elementProperties){let n=this._$Eu(r,i);n!==void 0&&this._$Eh.set(n,r)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let r=[];if(Array.isArray(e)){let i=new Set(e.flat(1/0).reverse());for(let n of i)r.unshift(ot(n))}else e!==void 0&&r.push(ot(e));return r}static _$Eu(e,r){let i=r.attribute;return i===!1?void 0:typeof i=="string"?i:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,r=this.constructor.elementProperties;for(let i of r.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return zt(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,r,i){this._$AK(e,i)}_$ET(e,r){let i=this.constructor.elementProperties.get(e),n=this.constructor._$Eu(e,i);if(n!==void 0&&i.reflect===!0){let s=(i.converter?.toAttribute!==void 0?i.converter:at).toAttribute(r,i.type);this._$Em=e,s==null?this.removeAttribute(n):this.setAttribute(n,s),this._$Em=null}}_$AK(e,r){let i=this.constructor,n=i._$Eh.get(e);if(n!==void 0&&this._$Em!==n){let s=i.getPropertyOptions(n),a=typeof s.converter=="function"?{fromAttribute:s.converter}:s.converter?.fromAttribute!==void 0?s.converter:at;this._$Em=n;let p=a.fromAttribute(r,s.type);this[n]=p??this._$Ej?.get(n)??p,this._$Em=null}}requestUpdate(e,r,i,n=!1,s){if(e!==void 0){let a=this.constructor;if(n===!1&&(s=this[e]),i??=a.getPropertyOptions(e),!((i.hasChanged??Kt)(s,r)||i.useDefault&&i.reflect&&s===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,i))))return;this.C(e,r,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,r,{useDefault:i,reflect:n,wrapped:s},a){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??r??this[e]),s!==!0||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||i||(r=void 0),this._$AL.set(e,r)),n===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(r){Promise.reject(r)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[n,s]of this._$Ep)this[n]=s;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[n,s]of i){let{wrapped:a}=s,p=this[n];a!==!0||this._$AL.has(n)||p===void 0||this.C(n,void 0,s,p)}}let e=!1,r=this._$AL;try{e=this.shouldUpdate(r),e?(this.willUpdate(r),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(r)):this._$EM()}catch(i){throw e=!1,this._$EM(),i}e&&this._$AE(r)}willUpdate(e){}_$AE(e){this._$EO?.forEach(r=>r.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(r=>this._$ET(r,this[r])),this._$EM()}updated(e){}firstUpdated(e){}};H.elementStyles=[],H.shadowRootOptions={mode:"open"},H[ge("elementProperties")]=new Map,H[ge("finalized")]=new Map,ui?.({ReactiveElement:H}),(Ae.reactiveElementVersions??=[]).push("2.1.2");var dt=globalThis,Vt=t=>t,Re=dt.trustedTypes,Yt=Re?Re.createPolicy("lit-html",{createHTML:t=>t}):void 0,ct="$lit$",U=`lit$${Math.random().toFixed(9).slice(2)}$`,pt="?"+U,hi=`<${pt}>`,X=document,be=()=>X.createComment(""),ve=t=>t===null||typeof t!="object"&&typeof t!="function",ut=Array.isArray,Xt=t=>ut(t)||typeof t?.[Symbol.iterator]=="function",lt=`[ 	
\f\r]`,_e=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,qt=/-->/g,Gt=/>/g,J=RegExp(`>|${lt}(?:([^\\s"'>=/]+)(${lt}*=${lt}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Zt=/'/g,Jt=/"/g,er=/^(?:script|style|textarea|title)$/i,ht=t=>(e,...r)=>({_$litType$:t,strings:e,values:r}),l=ht(1),yn=ht(2),$n=ht(3),$=Symbol.for("lit-noChange"),c=Symbol.for("lit-nothing"),Qt=new WeakMap,Q=X.createTreeWalker(X,129);function tr(t,e){if(!ut(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return Yt!==void 0?Yt.createHTML(e):e}var rr=(t,e)=>{let r=t.length-1,i=[],n,s=e===2?"<svg>":e===3?"<math>":"",a=_e;for(let p=0;p<r;p++){let d=t[p],u,m,h=-1,g=0;for(;g<d.length&&(a.lastIndex=g,m=a.exec(d),m!==null);)g=a.lastIndex,a===_e?m[1]==="!--"?a=qt:m[1]!==void 0?a=Gt:m[2]!==void 0?(er.test(m[2])&&(n=RegExp("</"+m[2],"g")),a=J):m[3]!==void 0&&(a=J):a===J?m[0]===">"?(a=n??_e,h=-1):m[1]===void 0?h=-2:(h=a.lastIndex-m[2].length,u=m[1],a=m[3]===void 0?J:m[3]==='"'?Jt:Zt):a===Jt||a===Zt?a=J:a===qt||a===Gt?a=_e:(a=J,n=void 0);let _=a===J&&t[p+1].startsWith("/>")?" ":"";s+=a===_e?d+hi:h>=0?(i.push(u),d.slice(0,h)+ct+d.slice(h)+U+_):d+U+(h===-2?p:_)}return[tr(t,s+(t[r]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),i]},ye=class t{constructor({strings:e,_$litType$:r},i){let n;this.parts=[];let s=0,a=0,p=e.length-1,d=this.parts,[u,m]=rr(e,r);if(this.el=t.createElement(u,i),Q.currentNode=this.el.content,r===2||r===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(n=Q.nextNode())!==null&&d.length<p;){if(n.nodeType===1){if(n.hasAttributes())for(let h of n.getAttributeNames())if(h.endsWith(ct)){let g=m[a++],_=n.getAttribute(h).split(U),y=/([.?@])?(.*)/.exec(g);d.push({type:1,index:s,name:y[2],strings:_,ctor:y[1]==="."?Me:y[1]==="?"?De:y[1]==="@"?Le:te}),n.removeAttribute(h)}else h.startsWith(U)&&(d.push({type:6,index:s}),n.removeAttribute(h));if(er.test(n.tagName)){let h=n.textContent.split(U),g=h.length-1;if(g>0){n.textContent=Re?Re.emptyScript:"";for(let _=0;_<g;_++)n.append(h[_],be()),Q.nextNode(),d.push({type:2,index:++s});n.append(h[g],be())}}}else if(n.nodeType===8)if(n.data===pt)d.push({type:2,index:s});else{let h=-1;for(;(h=n.data.indexOf(U,h+1))!==-1;)d.push({type:7,index:s}),h+=U.length-1}s++}}static createElement(e,r){let i=X.createElement("template");return i.innerHTML=e,i}};function ee(t,e,r=t,i){if(e===$)return e;let n=i!==void 0?r._$Co?.[i]:r._$Cl,s=ve(e)?void 0:e._$litDirective$;return n?.constructor!==s&&(n?._$AO?.(!1),s===void 0?n=void 0:(n=new s(t),n._$AT(t,r,i)),i!==void 0?(r._$Co??=[])[i]=n:r._$Cl=n),n!==void 0&&(e=ee(t,n._$AS(t,e.values),n,i)),e}var Pe=class{constructor(e,r){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=r}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:r},parts:i}=this._$AD,n=(e?.creationScope??X).importNode(r,!0);Q.currentNode=n;let s=Q.nextNode(),a=0,p=0,d=i[0];for(;d!==void 0;){if(a===d.index){let u;d.type===2?u=new ie(s,s.nextSibling,this,e):d.type===1?u=new d.ctor(s,d.name,d.strings,this,e):d.type===6&&(u=new Ie(s,this,e)),this._$AV.push(u),d=i[++p]}a!==d?.index&&(s=Q.nextNode(),a++)}return Q.currentNode=X,n}p(e){let r=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(e,i,r),r+=i.strings.length-2):i._$AI(e[r])),r++}},ie=class t{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,r,i,n){this.type=2,this._$AH=c,this._$AN=void 0,this._$AA=e,this._$AB=r,this._$AM=i,this.options=n,this._$Cv=n?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,r=this._$AM;return r!==void 0&&e?.nodeType===11&&(e=r.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,r=this){e=ee(this,e,r),ve(e)?e===c||e==null||e===""?(this._$AH!==c&&this._$AR(),this._$AH=c):e!==this._$AH&&e!==$&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):Xt(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==c&&ve(this._$AH)?this._$AA.nextSibling.data=e:this.T(X.createTextNode(e)),this._$AH=e}$(e){let{values:r,_$litType$:i}=e,n=typeof i=="number"?this._$AC(e):(i.el===void 0&&(i.el=ye.createElement(tr(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===n)this._$AH.p(r);else{let s=new Pe(n,this),a=s.u(this.options);s.p(r),this.T(a),this._$AH=s}}_$AC(e){let r=Qt.get(e.strings);return r===void 0&&Qt.set(e.strings,r=new ye(e)),r}k(e){ut(this._$AH)||(this._$AH=[],this._$AR());let r=this._$AH,i,n=0;for(let s of e)n===r.length?r.push(i=new t(this.O(be()),this.O(be()),this,this.options)):i=r[n],i._$AI(s),n++;n<r.length&&(this._$AR(i&&i._$AB.nextSibling,n),r.length=n)}_$AR(e=this._$AA.nextSibling,r){for(this._$AP?.(!1,!0,r);e!==this._$AB;){let i=Vt(e).nextSibling;Vt(e).remove(),e=i}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},te=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,r,i,n,s){this.type=1,this._$AH=c,this._$AN=void 0,this.element=e,this.name=r,this._$AM=n,this.options=s,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=c}_$AI(e,r=this,i,n){let s=this.strings,a=!1;if(s===void 0)e=ee(this,e,r,0),a=!ve(e)||e!==this._$AH&&e!==$,a&&(this._$AH=e);else{let p=e,d,u;for(e=s[0],d=0;d<s.length-1;d++)u=ee(this,p[i+d],r,d),u===$&&(u=this._$AH[d]),a||=!ve(u)||u!==this._$AH[d],u===c?e=c:e!==c&&(e+=(u??"")+s[d+1]),this._$AH[d]=u}a&&!n&&this.j(e)}j(e){e===c?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},Me=class extends te{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===c?void 0:e}},De=class extends te{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==c)}},Le=class extends te{constructor(e,r,i,n,s){super(e,r,i,n,s),this.type=5}_$AI(e,r=this){if((e=ee(this,e,r,0)??c)===$)return;let i=this._$AH,n=e===c&&i!==c||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,s=e!==c&&(i===c||n);n&&this.element.removeEventListener(this.name,this,i),s&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},Ie=class{constructor(e,r,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=r,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){ee(this,e)}},ir={M:ct,P:U,A:pt,C:1,L:rr,R:Pe,D:Xt,V:ee,I:ie,H:te,N:De,U:Le,B:Me,F:Ie},mi=dt.litHtmlPolyfillSupport;mi?.(ye,ie),(dt.litHtmlVersions??=[]).push("3.3.3");var nr=(t,e,r)=>{let i=r?.renderBefore??e,n=i._$litPart$;if(n===void 0){let s=r?.renderBefore??null;i._$litPart$=n=new ie(e.insertBefore(be(),s),s,void 0,r??{})}return n._$AI(t),n};var mt=globalThis,E=class extends H{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let r=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=nr(r,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return $}};E._$litElement$=!0,E.finalized=!0,mt.litElementHydrateSupport?.({LitElement:E});var fi=mt.litElementPolyfillSupport;fi?.({LitElement:E});(mt.litElementVersions??=[]).push("4.2.2");var x={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},W=t=>(...e)=>({_$litDirective$:t,values:e}),C=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,r,i){this._$Ct=e,this._$AM=r,this._$Ci=i}_$AS(e,r){return this.update(e,r)}update(e,r){return this.render(...r)}};var{I:gi}=ir,sr=t=>t;var ar=t=>t.strings===void 0,or=()=>document.createComment(""),ne=(t,e,r)=>{let i=t._$AA.parentNode,n=e===void 0?t._$AB:e._$AA;if(r===void 0){let s=i.insertBefore(or(),n),a=i.insertBefore(or(),n);r=new gi(s,a,t,t.options)}else{let s=r._$AB.nextSibling,a=r._$AM,p=a!==t;if(p){let d;r._$AQ?.(t),r._$AM=t,r._$AP!==void 0&&(d=t._$AU)!==a._$AU&&r._$AP(d)}if(s!==n||p){let d=r._$AA;for(;d!==s;){let u=sr(d).nextSibling;sr(i).insertBefore(d,n),d=u}}}return r},j=(t,e,r=t)=>(t._$AI(e,r),t),_i={},Oe=(t,e=_i)=>t._$AH=e,lr=t=>t._$AH,Fe=t=>{t._$AR(),t._$AA.remove()};var dr=(t,e,r)=>{let i=new Map;for(let n=e;n<=r;n++)i.set(t[n],n);return i},K=W(class extends C{constructor(t){if(super(t),t.type!==x.CHILD)throw Error("repeat() can only be used in text expressions")}dt(t,e,r){let i;r===void 0?r=e:e!==void 0&&(i=e);let n=[],s=[],a=0;for(let p of t)n[a]=i?i(p,a):a,s[a]=r(p,a),a++;return{values:s,keys:n}}render(t,e,r){return this.dt(t,e,r).values}update(t,[e,r,i]){let n=lr(t),{values:s,keys:a}=this.dt(e,r,i);if(!Array.isArray(n))return this.ut=a,s;let p=this.ut??=[],d=[],u,m,h=0,g=n.length-1,_=0,y=s.length-1;for(;h<=g&&_<=y;)if(n[h]===null)h++;else if(n[g]===null)g--;else if(p[h]===a[_])d[_]=j(n[h],s[_]),h++,_++;else if(p[g]===a[y])d[y]=j(n[g],s[y]),g--,y--;else if(p[h]===a[y])d[y]=j(n[h],s[y]),ne(t,d[y+1],n[h]),h++,y--;else if(p[g]===a[_])d[_]=j(n[g],s[_]),ne(t,n[h],n[g]),g--,_++;else if(u===void 0&&(u=dr(a,_,y),m=dr(p,h,g)),u.has(p[h]))if(u.has(p[g])){let N=m.get(a[_]),nt=N!==void 0?n[N]:null;if(nt===null){let Ht=ne(t,n[h]);j(Ht,s[_]),d[_]=Ht}else d[_]=j(nt,s[_]),ne(t,n[h],nt),n[N]=null;_++}else Fe(n[g]),g--;else Fe(n[h]),h++;for(;_<=y;){let N=ne(t,d[y+1]);j(N,s[_]),d[_++]=N}for(;h<=g;){let N=n[h++];N!==null&&Fe(N)}return this.ut=a,Oe(t,d),$}});var cr="important",bi=" !"+cr,A=W(class extends C{constructor(t){if(super(t),t.type!==x.ATTRIBUTE||t.name!=="style"||t.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(t){return Object.keys(t).reduce((e,r)=>{let i=t[r];return i==null?e:e+`${r=r.includes("-")?r:r.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${i};`},"")}update(t,[e]){let{style:r}=t.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(e)),this.render(e);for(let i of this.ft)e[i]==null&&(this.ft.delete(i),i.includes("-")?r.removeProperty(i):r[i]=null);for(let i in e){let n=e[i];if(n!=null){this.ft.add(i);let s=typeof n=="string"&&n.endsWith(bi);i.includes("-")||s?r.setProperty(i,s?n.slice(0,-11):n,s?cr:""):r[i]=n}}return $}});var S=W(class extends C{constructor(t){if(super(t),t.type!==x.PROPERTY&&t.type!==x.ATTRIBUTE&&t.type!==x.BOOLEAN_ATTRIBUTE)throw Error("The `live` directive is not allowed on child or event bindings");if(!ar(t))throw Error("`live` bindings can only contain a single expression")}render(t){return t}update(t,[e]){if(e===$||e===c)return e;let r=t.element,i=t.name;if(t.type===x.PROPERTY){if(e===r[i])return $}else if(t.type===x.BOOLEAN_ATTRIBUTE){if(!!e===r.hasAttribute(i))return $}else if(t.type===x.ATTRIBUTE&&r.getAttribute(i)===e+"")return $;return Oe(t),e}});var pr="parcels";function V(t,e,r){return t.callService(pr,e,r,void 0,!1)}function Ne(t,e,r={}){return t.callWS({...r,type:`${pr}/${e}`})}var Y={amazon:"Amazon Logistics",asendia:"Asendia",bpost:"bpost",brt:"BRT",cainiao:"Cainiao",chronopost:"Chronopost",colissimo:"Colissimo",correos:"Correos",correos_express:"Correos Express",ctt:"CTT",ctt_expresso:"CTT Expresso",deutsche_post:"Deutsche Post",dhl:"DHL",dpd:"DPD",evri:"Evri",fedex:"FedEx",gls:"GLS",hermes:"Hermes",inpost:"InPost",la_poste:"La Poste",mondial_relay:"Mondial Relay",mrw:"MRW",nacex:"Nacex",paack:"Paack",postnl:"PostNL",poste_italiane:"Poste Italiane",royal_mail:"Royal Mail",sda:"SDA",seur:"SEUR",tnt:"TNT",ups:"UPS",usps:"USPS",vinted_go:"Vinted Go",yunexpress:"YunExpress",other:"Other"};function He(){return Object.entries(Y).filter(([t])=>t!=="other").map(([t,e])=>({id:t,name:e})).sort((t,e)=>t.name.localeCompare(e.name,"en",{sensitivity:"base"})).concat([{id:"other",name:Y.other??"Other"}])}function ur(t){return Object.hasOwn(Y,t)?Y[t]??t:t}var o={weekCardName:"Parcels week",weekCardDescription:"A Monday to Sunday calendar of your parcel deliveries.",listCardName:"Parcels without a date",listCardDescription:"Active parcels that don't have a delivery date yet.",reviewCardName:"Parcels review",reviewCardDescription:"E-mails that need a decision before Parcels uses them. Only shown to administrators.",defaultWeekTitle:"Parcels",defaultListTitle:"No date yet",defaultReviewTitle:"Parcels review",loading:"Loading parcels\u2026",loadError:"Couldn't load parcels: {message}",refreshError:"Couldn't update parcels: {message}",unknownError:"Unknown error",close:"Close",cancel:"Cancel",save:"Save",dismissMessage:"Dismiss message",configInvalid:"Invalid configuration: expected a map of options.",configTitle:'Invalid configuration: "title" must be text.',configShowArchived:'Invalid configuration: "show_archived" must be true or false.',previousWeek:"Previous week",nextWeek:"Next week",today:"Today",goToToday:"Go to the current week",weekNavigation:"Week navigation",weekOf:"Week of {range}",refresh:"Check mailboxes now",refreshFailed:"Couldn't check the mailboxes: {message}",addParcel:"Add parcel",noDeliveriesThisWeek:"No deliveries this week",noDeliveriesThisDay:"No deliveries",todayTag:"Today",privateParcel:"Private parcel",unnamedParcel:"Parcel",aiBadge:"AI",aiBadgeLabel:"found by the local AI",privateLabel:"private",autoMerged:"Auto-merged \u2014 check",autoMergedLabel:"merged automatically, please check",undo:"Undo",undoMergeLabel:"Undo the automatic merge of {title}",undoFailed:"Couldn't undo the merge: {message}",keep:"Keep",keepMergeLabel:"Keep the automatic merge of {title}",keepFailed:"Couldn't keep the merge: {message}",continuesBefore:"started before this week",continuesAfter:"continues after this week",deliveredOn:"delivered {date}",returnedOn:"returned {date}",expectedOn:"expected {date}",readyForPickupSince:"ready for pickup since {date}",statusOn:"{status} on {date}",windowFrom:"from {time}",windowUntil:"until {time}",noUndatedParcels:"Every active parcel has a delivery date.",tabReview:"Needs review",tabFiltered:"Filtered",tabCount:"{label} ({count})",reviewTabs:"Review lists",emptyReview:"Nothing to review.",emptyFiltered:"No filtered e-mails.",filteredHint:"E-mails the local AI classed as not about a parcel.",receivedOn:"Received {date}",noSubject:"(no subject)",mailboxOf:"Mailbox: {owner}",reasonIs:"Reason: {reason}",unverifiedSender:"Unverified sender",unverifiedSenderHint:"This e-mail didn't pass the sender checks (DKIM/DMARC). Make sure it's genuine before you accept it.",aiSuggestionLabel:"read by the local AI",suggestion:"Suggestion",noSuggestion:"No suggestion. Use Edit to enter the details yourself.",accept:"Accept",acceptWithChanges:"Accept with changes",edit:"Edit",dismiss:"Dismiss",trustSender:"Trust this sender",trustSenderHint:"Treat e-mails from {domain} as a known sender from now on",ignoreSender:"Ignore this sender",ignoreSenderHint:"Skip e-mails from {domain} from now on",restore:"Restore",fieldKind:"Type",fieldMerchant:"Merchant",fieldCarrier:"Carrier",fieldTrackingNumber:"Tracking number",fieldTrackingNumbers:"Tracking numbers",fieldOrderNumbers:"Order numbers",fieldEtaStart:"Expected from",fieldEtaEnd:"Expected until",fieldWindowStart:"Time window from",fieldWindowEnd:"Time window until",fieldPickupPoint:"Pickup point",fieldPickupCode:"Pickup code",fieldItems:"Items",fieldPrivate:"Private (only the owners can see it)",hintList:"Separate with commas or new lines.",hintItems:"One per line.",carrierAuto:"Detect automatically",carrierUnknown:"Unknown",details:"Parcel details",status:"Status",sinceDate:"since {date}",carrier:"Carrier",trackOnline:"Track on the carrier's site",opensInNewTab:"(opens in a new tab)",trackingNumber:"Tracking number",copy:"Copy",copyTrackingNumber:"Copy the tracking number",copied:"Copied.",copyFailed:"Couldn't copy automatically. The number is selected, so you can copy it yourself.",merchant:"Merchant",orders:"Orders",items:"Items",expected:"Expected",timeWindow:"Time window",pickupPoint:"Pickup point",pickupCode:"Pickup code",delivered:"Delivered",timeline:"Timeline",noTimeline:"No events yet.",provisional:"Provisional",provisionalHint:"Made from an order e-mail. It's completed when the shipping e-mail arrives.",archived:"Archived",private:"Private",loadingDetails:"Loading details\u2026",detailsError:"Couldn't load the details: {message}",retry:"Try again",notFound:"This parcel no longer exists.",aiNotice:"Found by the local AI. Check the details, then confirm them.",confirm:"Confirm",confirmLabel:"Confirm the details the local AI found",mergedNotice:"Merged automatically ({reason}). Check that it's one parcel.",mergedNoticeNoReason:"Merged automatically. Check that it's one parcel.",markDelivered:"Mark delivered",editDate:"Edit date",mergeWith:"Merge with\u2026",split:"Split\u2026",archive:"Archive",actions:"Actions",mergeIntro:"Choose the parcel to merge into this one.",mergeChoose:"Parcel",mergeConfirm:"Merge",noMergeCandidates:"There are no other active parcels to merge with.",splitIntro:"Choose what to move to a new parcel.",splitConfirm:"Split off",splitHint:"Choose at least one, but not all of them.",archiveQuestion:"Archive this parcel? It no longer counts as active.",dateEndBeforeStart:"The end date is before the start date.",dateEndWithoutStart:"Set a start date too.",windowEndBeforeStart:"The time window must end after it starts.",actionFailed:"That didn't work: {message}",addTitle:"Add parcel",addSubmit:"Add",trackingRequired:"Enter a tracking number."},hr={ordered:"Ordered",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",exception:"Problem with delivery",ready_for_pickup:"Ready for pickup",returned:"Returned",cancelled:"Cancelled"},Ue={order:"Order confirmation",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",ready_for_pickup:"Ready for pickup",delayed:"Delayed",customs:"Held at customs",return:"Return",cancelled:"Cancelled",not_parcel:"Not about a parcel",unknown:"Unknown"},mr={parser:"E-mail",ai:"Local AI",manual:"Added by hand",seventeentrack:"17TRACK"},fr={unknown_sender:"Unknown sender",not_aligned:"The sender's domain isn't authenticated (DKIM/DMARC)",no_auth_header:"No authentication results in the e-mail",untrusted_authserv:"Authentication results from an unknown server",low_confidence:"Not sure about the details",unknown_format:"Unknown e-mail format",ai_suggestion:"Read by the local AI",ai_unavailable:"The local AI wasn't available",ai_rejected:"The local AI's answer didn't pass the checks",restored:"Moved back from Filtered"},gr={same_number:"same tracking number",same_merchant_eta:"same shop and delivery date"};function f(t,e){return t.replace(/\{(\w+)\}/g,(r,i)=>Object.hasOwn(e,i)?String(e[i]):r)}function R(t){if(typeof t=="string"&&t.trim())return t;if(t&&typeof t=="object"){let e=t.message;if(typeof e=="string"&&e.trim())return e;let r=t.code;if(typeof r=="string"&&r.trim())return r}return o.unknownError}var vi=["a[href]","button:not([disabled])","input:not([disabled]):not([type='hidden'])","select:not([disabled])","textarea:not([disabled])","[tabindex]:not([tabindex='-1'])"].join(",");function yi(t){return[...t.querySelectorAll(vi)].filter(e=>!e.closest("[hidden], [inert]")&&e.getClientRects().length>0)}function _r(t,e){if(t.key!=="Tab"||t.altKey||t.ctrlKey||t.metaKey)return;let r=yi(e),i=r[0],n=r[r.length-1];if(!i||!n){t.preventDefault(),e.focus();return}let a=e.getRootNode().activeElement,p=a instanceof HTMLElement&&e.contains(a)&&a!==e;t.shiftKey&&(!p||a===i)?(t.preventDefault(),n.focus()):!t.shiftKey&&(!p||a===n)&&(t.preventDefault(),i.focus())}var $i="parcels-error",se=class extends E{static properties={hass:{attribute:!1},_open:{state:!0},_busy:{state:!0},_error:{state:!0}};_returnFocus=null;_pressedBackdrop=!1;_hadFocus=!1;_session=0;constructor(){super(),this.hass=void 0,this._open=!1,this._busy=!1,this._error=null}render(){return l`<dialog
      aria-labelledby="dialog-title"
      @close=${this._onClose}
      @keydown=${this._onKeyDown}
      @pointerdown=${this._onPointerDown}
      @click=${this._onClick}
    >
      ${this._open?this.renderContent():c}
    </dialog>`}renderContent(){return c}canLightDismiss(){return!this._busy}dialogClosed(){}get isOpen(){return this._open}async showDialog(e){this._session+=1,this._returnFocus=e,this._open=!0,this._busy=!1,this._error=null,await this.updateComplete;let r=this._dialog();!r||!this._open||!this.isConnected||(r.open||r.showModal(),this.focusInDialog("[data-autofocus]"))}closeDialog(){let e=this._dialog();e?.open&&e.close(),this._finishClose(!0)}focusInDialog(e){this.renderRoot.querySelector(`dialog ${e}`)?.focus()}async focusAfterRender(e){await this.updateComplete,this._open&&this.focusInDialog(e)}async runAction(e,r){if(this._busy)return;let i=this._session;this._busy=!0,this._error=null;try{await e(),this._open&&this._session===i&&r?.()}catch(n){let s=f(o.actionFailed,{message:R(n)});this._open&&this._session===i?this._error=s:this.dispatchEvent(new CustomEvent($i,{detail:s}))}finally{this._session===i&&(this._busy=!1)}}disconnectedCallback(){super.disconnectedCallback(),this._finishClose(!1)}willUpdate(e){this._hadFocus=this._open&&!!this.shadowRoot?.activeElement}updated(e){this._hadFocus&&this._open&&!this.shadowRoot?.activeElement&&this.focusInDialog("[data-autofocus]"),this._hadFocus=!1}_dialog(){return this.renderRoot.querySelector("dialog")}_finishClose(e){if(!this._open)return;let r=this._returnFocus;this._returnFocus=null,this._open=!1,this._busy=!1,this._error=null,this._pressedBackdrop=!1,this.dialogClosed(),e&&r?.()}_onClose(e){let r=e.currentTarget;e.target===r&&!r.open&&this._finishClose(!0)}_onKeyDown(e){_r(e,e.currentTarget)}_onPointerDown(e){this._pressedBackdrop=e.target===e.currentTarget}_onClick(e){let r=this._pressedBackdrop&&e.target===e.currentTarget;this._pressedBackdrop=!1,r&&this.canLightDismiss()&&this.closeDialog()}};var wi=/^(\d{4})-(\d{2})-(\d{2})$/,xi=/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)(?:[.,](\d+))?(Z|[+-]\d{2}(?::?\d{2})?)?$/i,ki=[31,28,31,30,31,30,31,31,30,31,30,31];function Si(t){return t%4===0&&t%100!==0||t%400===0}function Ti(t,e){return e===2&&Si(t)?29:ki[e-1]??0}function We(t){if(typeof t!="string")return null;let e=wi.exec(t);if(!e)return null;let r=Number(e[1]),i=Number(e[2]),n=Number(e[3]);return i<1||i>12||n<1||n>Ti(r,i)?null:{year:r,month:i,day:n}}function q(t){return We(t)!==null}function Be(t){let e=We(t);if(!e)throw new RangeError(`Not a YYYY-MM-DD date: ${t}`);return e}function ze({year:t,month:e,day:r}){let i=e<=2?t-1:t,n=Math.floor(i/400),s=i-n*400,a=(e+9)%12,p=Math.floor((153*a+2)/5)+r-1,d=s*365+Math.floor(s/4)-Math.floor(s/100)+p;return n*146097+d-719468}function Ei(t){let e=t+719468,r=Math.floor(e/146097),i=e-r*146097,n=Math.floor((i-Math.floor(i/1460)+Math.floor(i/36524)-Math.floor(i/146096))/365),s=i-(365*n+Math.floor(n/4)-Math.floor(n/100)),a=Math.floor((5*s+2)/153),p=s-Math.floor((153*a+2)/5)+1,d=a<10?a+3:a-9;return{year:n+r*400+(d<=2?1:0),month:d,day:p}}function Ci({year:t,month:e,day:r}){return`${String(t).padStart(4,"0")}-${String(e).padStart(2,"0")}-${String(r).padStart(2,"0")}`}function oe(t,e){return Ci(Ei(ze(Be(t))+e))}function ft(t,e){return ze(Be(e))-ze(Be(t))}function Ai(t){return((ze(Be(t))+3)%7+7)%7}function vr(t){return oe(t,-Ai(t))}function yr(t){return Array.from({length:7},(e,r)=>oe(t,r))}function P(t,e){return t<e?-1:t>e?1:0}function $r(t,e){return P(t,e)>=0?t:e}function M(t){if(typeof t!="string")return null;let e=xi.exec(t.trim());if(!e)return null;let[,r,i,n,s]=e;if(!r||!i||!q(r))return null;let a=n?`.${n.slice(0,3).padEnd(3,"0")}`:"",p="Z";if(s&&s.toUpperCase()!=="Z"){let u=s.slice(1).replace(":","").padEnd(4,"0");p=`${s[0]}${u.slice(0,2)}:${u.slice(2,4)}`}let d=Date.parse(`${r}T${i}${a}${p}`);return Number.isNaN(d)?null:d}var br=new Map;function Ri(t){let e=br.get(t);if(!e){let r={calendar:"gregory",numberingSystem:"latn",year:"numeric",month:"2-digit",day:"2-digit"};try{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:t})}catch{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:"UTC"})}br.set(t,e)}return e}function $e(t,e){if(q(t))return t;let r=M(t);if(r===null)return null;let i="",n="",s="";for(let p of Ri(e).formatToParts(r))p.type==="year"?i=p.value:p.type==="month"?n=p.value:p.type==="day"&&(s=p.value);let a=`${i.padStart(4,"0")}-${n}-${s}`;return q(a)?a:null}function Pi(t){return[...new Set(t)]}function wr(t){return Pi(t.split(/[\n,;]+/).map(e=>e.trim()).filter(Boolean))}function Mi(t){return t.split(/\r?\n/).map(e=>e.trim()).filter(Boolean)}function L(t){let e=/^(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?$/.exec((t??"").trim());if(!e)return null;let r=Number(e[1]),i=Number(e[2]);return r>23||i>59?null:`${String(r).padStart(2,"0")}:${String(i).padStart(2,"0")}`}function D(t){let e=t.trim();return e||null}function Di(t,e){return e&&!t?o.dateEndWithoutStart:t&&e&&P(e,t)<0?o.dateEndBeforeStart:null}function Li(t,e){let r=L(t),i=L(e);return r&&i&&i<=r?o.windowEndBeforeStart:null}function xr(t){return{eta_start:t.eta_start??"",eta_end:t.eta_end??"",window_start:L(t.window_start)??"",window_end:L(t.window_end)??""}}function je(t){let e=Di(t.eta_start,t.eta_end);if(e)return{message:e,field:e===o.dateEndWithoutStart?"eta_start":"eta_end"};let r=Li(t.window_start,t.window_end);return r?{message:r,field:"window_end"}:null}function kr(t,e){return{parcel_id:t,eta_start:D(e.eta_start),eta_end:D(e.eta_end),window_start:L(e.window_start),window_end:L(e.window_end)}}var Sr="shipped";function gt(t){return{kind:t?.kind||Sr,merchant:t?.merchant??"",carrier:t?.carrier??"",tracking_numbers:(t?.tracking_numbers??[]).join(", "),order_numbers:(t?.order_numbers??[]).join(", "),eta_start:t?.eta_start??"",eta_end:t?.eta_end??"",window_start:L(t?.window_start)??"",window_end:L(t?.window_end)??"",pickup_point:t?.pickup_point??"",pickup_code:t?.pickup_code??"",items:(t?.items??[]).join(`
`)}}function Tr(t){return{kind:t.kind.trim()||Sr,merchant:D(t.merchant),carrier:D(t.carrier),tracking_numbers:wr(t.tracking_numbers),order_numbers:wr(t.order_numbers),eta_start:D(t.eta_start),eta_end:D(t.eta_end),window_start:L(t.window_start),window_end:L(t.window_end),pickup_point:D(t.pickup_point),pickup_code:D(t.pickup_code),items:Mi(t.items)}}function Er(t){let e=t.tracking_number.trim();if(!e)return null;let r={tracking_number:e},i=D(t.carrier);i&&(r.carrier=i);let n=D(t.merchant);return n&&(r.merchant=n),t.private&&(r.private=!0),r}function _t(t,e){return t.length>0&&t.length<e}var Ii="https://github.com/fratei/ha-parcels";function I(t,e){customElements.get(t)||customElements.define(t,e)}function ae(t,e,r){let i=window;Array.isArray(i.customCards)||(i.customCards=[]);let n=i.customCards;n.some(s=>s?.type===t)||n.push({type:t,name:e,description:r,preview:!0,documentationURL:Ii})}var O=w`
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
`,Ke=w`
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
`,Ve=w`
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
`;var Cr={tracking_number:"",carrier:"",merchant:"",private:!1},bt=class extends se{static properties={_form:{state:!0},_missingNumber:{state:!0}};static styles=[O,Ve,w`
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
    `];constructor(){super(),this._form=Cr,this._missingNumber=!1}async open(e=null){this._form=Cr,this._missingNumber=!1,await this.showDialog(e)}canLightDismiss(){return!1}renderContent(){let e=this._form,r=this._missingNumber;return l`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">${o.addTitle}</h2>
        </div>
        <button
          type="button"
          class="icon-btn"
          aria-label=${o.close}
          title=${o.close}
          @click=${this.closeDialog}
        >
          <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
        </button>
      </div>
      <div class="dialog-content">
        <form id="add-form" novalidate @submit=${this._submit}>
          <label class="field">
            <span class="field-label">${o.fieldTrackingNumber}</span>
            <input
              id="tracking-number"
              name="tracking_number"
              required
              autocomplete="off"
              autocapitalize="characters"
              spellcheck="false"
              data-autofocus
              .value=${S(e.tracking_number)}
              aria-invalid=${r?"true":"false"}
              aria-describedby=${r?"tracking-error":c}
              @input=${this._onInput}
            />
          </label>
          ${r?l`<p class="field-error" id="tracking-error">${o.trackingRequired}</p>`:c}
          <label class="field">
            <span class="field-label">${o.fieldCarrier}</span>
            <select name="carrier" @change=${this._onInput}>
              <option value="" ?selected=${e.carrier===""}>${o.carrierAuto}</option>
              ${He().map(i=>l`<option value=${i.id} ?selected=${e.carrier===i.id}>
                    ${i.name}
                  </option>`)}
            </select>
          </label>
          <label class="field">
            <span class="field-label">${o.fieldMerchant}</span>
            <input
              name="merchant"
              autocomplete="off"
              .value=${S(e.merchant)}
              @input=${this._onInput}
            />
          </label>
          <label class="check-row">
            <input
              type="checkbox"
              name="private"
              .checked=${S(e.private)}
              @change=${this._onInput}
            />
            <span>${o.fieldPrivate}</span>
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
        <button type="button" class="btn" @click=${this.closeDialog}>${o.cancel}</button>
        <button
          type="submit"
          form="add-form"
          class="btn primary"
          aria-disabled=${this._busy?"true":"false"}
        >
          ${o.addSubmit}
        </button>
      </div>
    `}_onInput(e){let r=e.currentTarget,i=r.name,n=r instanceof HTMLInputElement&&r.type==="checkbox"?r.checked:r.value;this._form={...this._form,[i]:n},i==="tracking_number"&&this._missingNumber&&r.value.trim()&&(this._missingNumber=!1)}_submit(e){e.preventDefault();let r=this.hass;if(!r||this._busy)return;let i=Er(this._form);if(!i){this._missingNumber=!0,this.focusAfterRender("#tracking-number");return}this.runAction(()=>V(r,"add",i),()=>this.closeDialog())}};I("parcels-add-dialog",bt);var vt=W(class extends C{constructor(t){if(super(t),t.type!==x.ATTRIBUTE||t.name!=="class"||t.strings?.length>2)throw Error("`classMap()` can only be used in the `class` attribute and must be the only part in the attribute.")}render(t){return" "+Object.keys(t).filter(e=>t[e]).join(" ")+" "}update(t,[e]){if(this.st===void 0){this.st=new Set,t.strings!==void 0&&(this.nt=new Set(t.strings.join(" ").split(/\s/).filter(i=>i!=="")));for(let i in e)e[i]&&!this.nt?.has(i)&&this.st.add(i);return this.render(e)}let r=t.element.classList;for(let i of this.st)i in e||(r.remove(i),this.st.delete(i));for(let i in e){let n=!!e[i];n===this.st.has(i)||this.nt?.has(i)||(n?(r.add(i),this.st.add(i)):(r.remove(i),this.st.delete(i)))}return $}});function Oi(t){try{return Intl.DateTimeFormat.supportedLocalesOf([t]),t}catch{return"en"}}function Fi(){let t=new Intl.DateTimeFormat(void 0,{hour:"numeric"}).resolvedOptions().hourCycle;return t==="h11"||t==="h12"}function qe(t,e){let r=Oi(t?.locale?.language||t?.language||"en"),i=t?.locale?.time_format,n;i==="12"?n=!0:i==="24"?n=!1:i==="system"&&(n=Fi());let s=t?.locale?.time_zone==="local"?void 0:e||t?.config?.time_zone||void 0;return{language:r,hour12:n,timeZone:s}}var Ar=new Map;function we(t,e,r){let i=e.hour!==void 0||e.timeStyle!==void 0,n={...e,timeZone:r?"UTC":t.timeZone};i&&t.hour12!==void 0&&(n.hour12=t.hour12);let s=JSON.stringify([t.language,n]),a=Ar.get(s);if(!a){try{a=new Intl.DateTimeFormat(t.language,n)}catch{a=new Intl.DateTimeFormat(t.language,{...n,timeZone:void 0})}Ar.set(s,a)}return a}function yt(t){let e=We(t);return e?new Date(Date.UTC(e.year,e.month-1,e.day)):null}var Rr={weekday:"short",day:"numeric",month:"short"},Pr={day:"numeric",month:"short",year:"numeric"};function re(t,e,r=Rr){let i=yt(t);return i?we(e,r,!0).format(i):t}function F(t,e,r,i=Rr){let n=yt(t),s=yt(e);return!n||!s?[t,e].filter(Boolean).join(" \u2013 "):t===e?we(r,i,!0).format(n):we(r,i,!0).formatRange(n,s)}function Ye(t,e){let r=/^(\d{1,2}):(\d{2})/.exec(t);if(!r)return t;let i=new Date(Date.UTC(1970,0,1,Number(r[1]),Number(r[2])));return we(e,{hour:"numeric",minute:"2-digit"},!0).format(i)}function le(t,e,r){return t&&e?`${Ye(t,r)}\u2013${Ye(e,r)}`:t?f(o.windowFrom,{time:Ye(t,r)}):e?f(o.windowUntil,{time:Ye(e,r)}):null}function B(t,e){if(!t)return"";let r=M(t);return r===null?t:we(e,{dateStyle:"medium",timeStyle:"short"},!1).format(r)}function xe(t){if(typeof t!="string")return null;let e=t.trim();return e||null}function Mr(t){let e=t.trim();if(!/^[a-z0-9]+(?:[_-][a-z0-9]+)*$/.test(e))return e;let r=e.replace(/[_-]+/g," ");return r.charAt(0).toUpperCase()+r.slice(1)}function ke(t,e){let r=xe(e);return r?Object.hasOwn(t,r)?t[r]??r:Mr(r):""}function de(t){let e=xe(t.carrier_name);if(e)return e;let r=xe(t.carrier);return!r||r==="other"?null:Object.hasOwn(Y,r)?ur(r):Mr(r)}function k(t){return t.restricted?o.privateParcel:xe(t.merchant)??de(t)??xe(t.tracking_number)??o.unnamedParcel}function Ge(t){let e=de(t);return e&&e!==k(t)?e:null}function G(t){return ke(hr,t)}function $t(t){return ke(Ue,t)}function wt(t){return ke(mr,t)}function Dr(t){return ke(fr,t)}function Lr(t){return ke(gr,t)}var Ze="var(--secondary-text-color, #727272)",Ir="var(--info-color, #039be5)",Ni="var(--warning-color, #ffa600)",Hi="var(--success-color, #43a047)",Or="var(--error-color, #db4437)",Ui="var(--purple-color, #926bc7)",Fr={ordered:Ze,shipped:Ir,in_transit:Ir,out_for_delivery:Ni,delivered:Hi,attempted:Or,exception:Or,ready_for_pickup:Ui,returned:Ze,cancelled:Ze};function Se(t){return Object.hasOwn(Fr,t)?Fr[t]:Ze}var Bi=new Set(["delivered","returned","cancelled"]);function Je(t){return!Bi.has(t)}function z(t){let e=q(t.eta_start)?t.eta_start:null,r=q(t.eta_end)?t.eta_end:null,i=e??r;return i?{start:i,end:r&&P(r,i)>=0?r:i}:null}function Nr(t){return Je(t.status)}function Hr(t,e){let r=M(t.status_time),i=M(e.status_time);return r!==i?r===null?1:i===null?-1:i-r:t.id<e.id?-1:t.id>e.id?1:0}function Ur(t){return t.filter(e=>Nr(e)&&!e.archived&&z(e)===null).sort(Hr)}function Qe(t,e){return t.filter(r=>r.id!==e&&Nr(r)&&!r.archived&&!r.restricted).sort(Hr)}function Br(t,e,r){return e?.kind==="delivered"||e?.kind==="returned"?null:le(t.window_start,t.window_end,r)}function zr(t,e){let r=e.placement??null,i=[];if(e.showStatus){let a=G(t.status);a&&i.push(a)}let n=Ge(t);n&&i.push(n),e.showRange&&r&&r.from!==r.to&&i.push(F(r.from,r.to,e.locale));let s=Br(t,r,e.locale);return s&&i.push(s),i.join(" \xB7 ")}function Wr(t,e){let{locale:r}=e,i=e.placement??null,n=[k(t)],s=Ge(t);s&&n.push(s);let a=G(t.status),p=i?re(i.from,r):"";switch(i?.kind){case"delivered":n.push(f(o.deliveredOn,{date:p}));break;case"returned":n.push(f(o.returnedOn,{date:p}));break;case"pickup":n.push(f(o.readyForPickupSince,{date:p}));break;case"status":n.push(f(o.statusOn,{status:a,date:p}));break;case"eta":a&&n.push(a),n.push(f(o.expectedOn,{date:F(i.from,i.to,r)}));break;default:a&&n.push(a);break}let d=Br(t,i,r);return d&&n.push(d),t.restricted||(t.ai&&n.push(o.aiBadgeLabel),t.auto_merged&&n.push(o.autoMergedLabel)),(t.private||t.restricted)&&n.push(o.privateLabel),e.continuesBefore&&n.push(o.continuesBefore),e.continuesAfter&&n.push(o.continuesAfter),n.join(", ")}function jr(t,e){let r=[k(t)],i=Ge(t);i&&r.push(i);let n=t.tracking_number?.trim();n&&n!==r[0]&&r.push(n);let s=z(t);return r.push(s?F(s.start,s.end,e):G(t.status)),r.filter(Boolean).join(" \xB7 ")}function xt(t){return`.chip[data-parcel-id="${CSS.escape(t)}"] button.chip-main`}function zi(t,e,r){let i=r.busy?"true":"false";return l`<div class="merge-note">
    <ha-icon icon="mdi:call-merge" aria-hidden="true"></ha-icon>
    <span class="merge-label">${o.autoMerged}</span>
    <button
      type="button"
      class="link-btn"
      aria-label=${f(o.undoMergeLabel,{title:e})}
      aria-disabled=${i}
      @click=${()=>r.onUndoMerge(t)}
    >
      ${o.undo}
    </button>
    <button
      type="button"
      class="link-btn"
      aria-label=${f(o.keepMergeLabel,{title:e})}
      aria-disabled=${i}
      @click=${()=>r.onKeepMerge(t)}
    >
      ${o.keep}
    </button>
  </div>`}function Xe(t,e){let{locale:r}=e,i=e.placement??null,n=k(t),s=Wr(t,{locale:r,placement:i,continuesBefore:e.continuesBefore,continuesAfter:e.continuesAfter}),a=zr(t,{locale:r,placement:i,showStatus:e.showStatus,showRange:e.showRange}),p={chip:!0,"cont-before":e.continuesBefore===!0,"cont-after":e.continuesAfter===!0,returned:t.status==="returned"},d={...e.position,"--chip-color":Se(t.status)},u=l`<span class="chip-row" aria-hidden=${t.restricted?"true":c}>
    ${e.continuesBefore?l`<span class="cont">‹</span>`:c}
    ${t.status==="delivered"?l`<span class="check">✓</span>`:c}
    <span class="chip-text">
      <span class="chip-title">${n}</span>
      ${a?l`<span class="chip-meta">${a}</span>`:c}
    </span>
    ${t.ai&&!t.restricted?l`<span class="badge ai">${o.aiBadge}</span>`:c}
    ${t.private||t.restricted?l`<ha-icon class="lock" icon="mdi:lock"></ha-icon>`:c}
    ${e.continuesAfter?l`<span class="cont">›</span>`:c}
  </span>`;return t.restricted?l`<div class=${vt(p)} style=${A(d)}>
      <div class="chip-main" title=${s}>
        <span class="sr-only">${s}</span>
        ${u}
      </div>
    </div>`:l`<div class=${vt(p)} style=${A(d)} data-parcel-id=${t.id}>
    <button
      type="button"
      class="chip-main"
      aria-haspopup="dialog"
      aria-label=${s}
      title=${s}
      @click=${m=>e.onOpen(t,m.currentTarget)}
    >
      ${u}
    </button>
    ${t.auto_merged?zi(t,n,e):c}
  </div>`}function T(t){return typeof t=="object"&&t!==null&&!Array.isArray(t)}function b(t){return typeof t=="string"?t:null}function v(t){return typeof t=="string"?t:""}function Z(t){return Array.isArray(t)?t.filter(e=>typeof e=="string"):[]}function pe(t){return typeof t=="string"&&t!==""?t:null}function ce(t,e){if(!Array.isArray(t))return[];let r=[];for(let i of t){let n=e(i);n!==null&&r.push(n)}return r}function kt(t){return t==="ai"||t==="manual"||t==="seventeentrack"?t:"parser"}function Wi(t){return!T(t)||!pe(t.origin)?null:{origin:v(t.origin),at:v(t.at),reason:v(t.reason)}}function Kr(t){if(!T(t))return null;let e=pe(t.id);return e?{id:e,merchant:b(t.merchant),carrier:b(t.carrier),carrier_name:b(t.carrier_name),tracking_number:b(t.tracking_number),tracking_url:b(t.tracking_url),status:v(t.status),status_time:b(t.status_time),eta_start:b(t.eta_start),eta_end:b(t.eta_end),window_start:b(t.window_start),window_end:b(t.window_end),delivered_at:b(t.delivered_at),pickup_point:b(t.pickup_point),pickup_code:b(t.pickup_code),order_numbers:Z(t.order_numbers),items:Z(t.items),private:t.private===!0,owners:Z(t.owners),source:kt(t.source),ai:t.ai===!0,auto_merged:Wi(t.auto_merged),provisional:t.provisional===!0,archived:t.archived===!0,origins:Z(t.origins),restricted:t.restricted===!0}:null}function ji(t){return T(t)?{kind:v(t.kind),merchant:b(t.merchant),carrier:b(t.carrier),tracking_numbers:Z(t.tracking_numbers),order_numbers:Z(t.order_numbers),eta_start:b(t.eta_start),eta_end:b(t.eta_end),window_start:b(t.window_start),window_end:b(t.window_end),pickup_point:b(t.pickup_point),pickup_code:b(t.pickup_code),items:Z(t.items)}:null}function Ki(t){if(!T(t))return null;let e=pe(t.id);return e?{id:e,created:v(t.created),received:b(t.received),sender:v(t.sender),sender_domain:v(t.sender_domain),subject:v(t.subject),mailbox_owner:b(t.mailbox_owner),reason:v(t.reason),authenticated:t.authenticated===!0,source:t.source==="ai"?"ai":"parser",suggestion:ji(t.suggestion)}:null}function Vi(t){if(!T(t))return null;let e=pe(t.id);return e?{id:e,created:v(t.created),received:b(t.received),sender:v(t.sender),sender_domain:v(t.sender_domain),subject:v(t.subject)}:null}function Yi(t){return t==="suggest"||t==="auto"?t:"off"}function qi(t,e=Date.now()){let r=T(t)?t:{},i=pe(r.time_zone)??"UTC",n=q(r.today)?r.today:$e(new Date(e).toISOString(),i)??"1970-01-01";return{user_is_admin:r.user_is_admin===!0,ai_enabled:r.ai_enabled===!0,ai_mode:Yi(r.ai_mode),dashboard_url:v(r.dashboard_url),seventeentrack:r.seventeentrack===!0,time_zone:i,today:n}}function Vr(t,e=Date.now()){let r=T(t)?t:{};return{parcels:ce(r.parcels,Kr),review:ce(r.review,Ki),filtered:ce(r.filtered,Vi),settings:qi(r.settings,e)}}function Gi(t){return T(t)?{time:v(t.time),status:v(t.status),source:kt(t.source),label:v(t.label)}:null}function Zi(t){return T(t)?{id:v(t.id),merchant:b(t.merchant),number:v(t.number),placed_at:b(t.placed_at),parcel_ids:Z(t.parcel_ids)}:null}function Ji(t){if(!T(t))return null;let e=pe(t.id);return e?{id:e,label:v(t.label),source:kt(t.source),time:b(t.time)}:null}function Yr(t){if(!T(t))return null;let e=Kr(t.parcel);return e?{parcel:e,timeline:ce(t.timeline,Gi),orders:ce(t.orders,Zi),origins:ce(t.origins,Ji)}:null}function qr(t){if(typeof t!="string")return null;let e=t.trim();if(!e)return null;let r;try{r=new URL(e)}catch{return null}return r.protocol!=="https:"||!r.hostname||r.username||r.password?null:r.href}var Qi={weekday:"short",day:"numeric",month:"short",year:"numeric"},Gr={eta_start:"",eta_end:"",window_start:"",window_end:""};function Xi(t){return t.map((e,r)=>({entry:e,index:r,time:M(e.time)??-1/0})).sort((e,r)=>r.time-e.time||r.index-e.index).map(({entry:e})=>e)}var St=class extends se{static properties={snapshot:{attribute:!1},locale:{attribute:!1},_parcelId:{state:!0},_details:{state:!0},_loading:{state:!0},_loadError:{state:!0},_mode:{state:!0},_copyState:{state:!0},_dateForm:{state:!0},_formError:{state:!0},_mergeTarget:{state:!0},_splitSelection:{state:!0},_pendingPrivate:{state:!0}};static styles=[O,Ve,w`
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
    `];_request=0;_loadedKey="";constructor(){super(),this.snapshot=null,this.locale=qe(void 0),this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._copyState="idle",this._dateForm=Gr,this._formError=null,this._mergeTarget="",this._splitSelection=[],this._pendingPrivate=null}async open(e,r=null){this._parcelId=e,this._details=null,this._loadError=null,this._mode="view",this._copyState="idle",this._formError=null,this._pendingPrivate=null,this._load(),await this.showDialog(r)}dialogClosed(){this._request+=1,this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._pendingPrivate=null}canLightDismiss(){return this._mode==="view"&&!this._busy}willUpdate(e){if(super.willUpdate(e),!e.has("snapshot")||!this.isOpen||!this.snapshot)return;this._pendingPrivate=null;let r=this.snapshot.parcels.find(i=>i.id===this._parcelId);r&&JSON.stringify(r)!==this._loadedKey&&this._load()}get _parcel(){let e=this._parcelId;return e===null?null:this.snapshot?this.snapshot.parcels.find(r=>r.id===e)??null:this._details?.parcel??null}async _load(){let e=this.hass,r=this._parcelId;if(!e||r===null)return;let i=++this._request,n=this.snapshot?.parcels.find(s=>s.id===r);this._loadedKey=n?JSON.stringify(n):"",this._loading=!0,this._loadError=null;try{let s=await Ne(e,"get",{parcel_id:r});if(i!==this._request)return;let a=Yr(s);if(!a)throw new Error(o.unknownError);this._details=a}catch(s){i===this._request&&(this._loadError=R(s))}finally{i===this._request&&(this._loading=!1)}}renderContent(){let e=this._parcel;return l`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">
            ${e?k(e):o.details}
          </h2>
          ${e?this._renderBadges(e):c}
        </div>
        <button
          type="button"
          class="icon-btn"
          data-autofocus
          aria-label=${o.close}
          title=${o.close}
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
      ${e.ai&&!e.restricted?l`<span class="badge ai" title=${o.aiBadgeLabel}>
            ${o.aiBadge}<span class="sr-only">, ${o.aiBadgeLabel}</span>
          </span>`:c}
      ${e.private||e.restricted?l`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${o.private}
          </span>`:c}
      ${e.provisional?l`<span class="badge info">${o.provisional}</span>`:c}
      ${e.archived?l`<span class="badge">${o.archived}</span>`:c}
    </div>`}_renderBody(e){if(!e)return this.snapshot||!this._loading&&!this._loadError?l`<p class="empty">${o.notFound}</p>`:this._renderLoadState();switch(this._mode){case"date":return this._renderDateForm();case"merge":return this._renderMerge(e);case"split":return this._renderSplit();case"archive":return l`<p>${o.archiveQuestion}</p>`;default:return this._renderView(e)}}_renderLoadState(){return this._loadError?l`<div class="alert error" role="alert">
        <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
        <span class="grow">${f(o.detailsError,{message:this._loadError})}</span>
        <button type="button" class="btn" @click=${this._load}>${o.retry}</button>
      </div>`:l`<p class="empty" role="status">${o.loadingDetails}</p>`}_renderView(e){let r=e.restricted;return l`
      ${!r&&e.ai?l`<div class="alert">
            <ha-icon icon="mdi:robot-outline" aria-hidden="true"></ha-icon>
            <span class="grow">${o.aiNotice}</span>
            <button
              type="button"
              class="btn"
              aria-label=${o.confirmLabel}
              aria-disabled=${this._busy?"true":"false"}
              @click=${this._confirm}
            >
              ${o.confirm}
            </button>
          </div>`:c}
      ${!r&&e.auto_merged?this._renderMergeNotice(e):c}
      ${!r&&e.provisional?l`<p class="hint">${o.provisionalHint}</p>`:c}
      ${this._renderFacts(e)}
      ${r?c:l`<label class="check-row switch-row">
            <input
              type="checkbox"
              role="switch"
              .checked=${S(this._pendingPrivate??e.private)}
              aria-disabled=${this._busy?"true":"false"}
              @click=${this._onPrivateClick}
              @change=${this._togglePrivate}
            />
            <span>${o.fieldPrivate}</span>
          </label>`}
      <h3 class="section-title">${o.timeline}</h3>
      ${this._details?this._renderTimeline(this._details.timeline):this._renderLoadState()}
    `}_renderMergeNotice(e){let r=Lr(e.auto_merged?.reason),i=this._busy?"true":"false",n=k(e);return l`<div class="alert warning">
      <ha-icon icon="mdi:call-merge" aria-hidden="true"></ha-icon>
      <span class="grow">
        ${r?f(o.mergedNotice,{reason:r}):o.mergedNoticeNoReason}
      </span>
      <button
        type="button"
        class="btn"
        aria-label=${f(o.undoMergeLabel,{title:n})}
        aria-disabled=${i}
        @click=${this._undoMerge}
      >
        ${o.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${f(o.keepMergeLabel,{title:n})}
        aria-disabled=${i}
        @click=${this._keepMerge}
      >
        ${o.keep}
      </button>
    </div>`}_renderFacts(e){let r=this.locale,i=z(e),n=le(e.window_start,e.window_end,r),s=de(e),a=e.restricted?null:qr(e.tracking_url),p=e.tracking_number?.trim()??"",d=this._details?.orders??[],u=(h,g)=>l`<div><dt>${h}</dt><dd>${g}</dd></div>`,m=e.status_time?` \xB7 ${f(o.sinceDate,{date:B(e.status_time,r)})}`:"";return l`<dl class="facts">
      ${u(o.status,`${G(e.status)}${m}`)}
      ${e.delivered_at?u(o.delivered,B(e.delivered_at,r)):c}
      ${i?u(o.expected,F(i.start,i.end,r,Qi)):c}
      ${n?u(o.timeWindow,n):c}
      ${s||a?u(o.carrier,l`${s??""}${a?l`<a class="link" href=${a} target="_blank" rel="noopener noreferrer">
                  ${o.trackOnline}<span class="sr-only"> ${o.opensInNewTab}</span>
                  <ha-icon icon="mdi:open-in-new" aria-hidden="true"></ha-icon>
                </a>`:c}`):c}
      ${p?l`<div>
            <dt><label for="tracking-number">${o.trackingNumber}</label></dt>
            <dd class="copy-row">
              <input id="tracking-number" readonly .value=${p} spellcheck="false" />
              <button
                type="button"
                class="btn"
                aria-label=${o.copyTrackingNumber}
                @click=${this._copy}
              >
                <ha-icon icon="mdi:content-copy" aria-hidden="true"></ha-icon>${o.copy}
              </button>
              <span class="copy-status hint" role="status">
                ${this._copyState==="copied"?o.copied:this._copyState==="failed"?o.copyFailed:""}
              </span>
            </dd>
          </div>`:c}
      ${e.merchant?u(o.merchant,e.merchant):c}
      ${d.length?u(o.orders,l`<ul>
              ${d.map(h=>l`<li>
                    ${h.number}${h.placed_at?` \xB7 ${B(h.placed_at,r)}`:""}
                  </li>`)}
            </ul>`):e.order_numbers.length?u(o.orders,e.order_numbers.join(", ")):c}
      ${e.items.length?u(o.items,l`<ul>
              ${e.items.map(h=>l`<li>${h}</li>`)}
            </ul>`):c}
      ${e.pickup_point?u(o.pickupPoint,e.pickup_point):c}
      ${e.pickup_code?u(o.pickupCode,e.pickup_code):c}
    </dl>`}_renderTimeline(e){if(!e.length)return l`<p class="muted">${o.noTimeline}</p>`;let r=this.locale;return l`<ol class="timeline">
      ${Xi(e).map(i=>{let n=G(i.status),s=i.label.trim(),a=[B(i.time,r),wt(i.source)].filter(Boolean).join(" \xB7 ");return l`<li style=${A({"--dot-color":Se(i.status)})}>
          <span class="dot" aria-hidden="true"></span>
          <div class="entry-title">${n}</div>
          ${s&&s!==n?l`<div>${s}</div>`:c}
          ${a?l`<div class="entry-meta">${a}</div>`:c}
        </li>`})}
    </ol>`}_renderDateForm(){let e=this._dateForm,r=this._formError,i=(n,s,a,p=!1)=>{let d=r?.field===n;return l`<label class="field">
        <span class="field-label">${s}</span>
        <input
          type=${a}
          name=${n}
          .value=${S(e[n])}
          ?data-first=${p}
          aria-invalid=${d?"true":"false"}
          aria-describedby=${d?"date-error":c}
          @input=${this._onDateInput}
        />
      </label>`};return l`<form id="date-form" novalidate @submit=${this._saveDate}>
      <div class="form-grid">
        ${i("eta_start",o.fieldEtaStart,"date",!0)}
        ${i("eta_end",o.fieldEtaEnd,"date")}
        ${i("window_start",o.fieldWindowStart,"time")}
        ${i("window_end",o.fieldWindowEnd,"time")}
      </div>
      ${r?l`<div class="alert error" id="date-error" role="alert">
            <span class="grow">${r.message}</span>
          </div>`:c}
    </form>`}_renderMerge(e){let r=Qe(this.snapshot?.parcels??[],e.id);if(!r.length)return l`<p class="empty">${o.noMergeCandidates}</p>`;let i=this._resolvedMergeTarget(r);return l`<p>${o.mergeIntro}</p>
      <label class="field">
        <span class="field-label">${o.mergeChoose}</span>
        <select data-first @change=${this._onMergeTarget}>
          ${r.map(n=>l`<option value=${n.id} ?selected=${n.id===i}>
                ${jr(n,this.locale)}
              </option>`)}
        </select>
      </label>`}_renderSplit(){let e=this._details?.origins??[],r=this.locale;return l`<fieldset aria-describedby="split-hint">
        <legend>${o.splitIntro}</legend>
        ${e.map((i,n)=>{let s=i.time?B(i.time,r):"";return l`<label class="check-row">
            <input
              type="checkbox"
              .value=${i.id}
              .checked=${S(this._splitSelection.includes(i.id))}
              ?data-first=${n===0}
              @change=${this._onSplitChange}
            />
            <span>
              ${i.label.trim()||wt(i.source)}${s?l`<span class="muted"> · ${s}</span>`:c}
            </span>
          </label>`})}
      </fieldset>
      <p class="hint" id="split-hint">${o.splitHint}</p>`}_renderActions(e){let r=this._busy?"true":"false",i=l`<button type="button" class="btn" data-cancel @click=${this._backToView}>
      ${o.cancel}
    </button>`;switch(this._mode){case"date":return l`<div class="dialog-actions">
          ${i}
          <button type="submit" form="date-form" class="btn primary" aria-disabled=${r}>
            ${o.save}
          </button>
        </div>`;case"merge":{let n=Qe(this.snapshot?.parcels??[],e.id);return l`<div class="dialog-actions">
          ${i}
          ${n.length?l`<button
                type="button"
                class="btn primary"
                aria-disabled=${r}
                @click=${this._merge}
              >
                ${o.mergeConfirm}
              </button>`:c}
        </div>`}case"split":{let n=_t(this._splitSelection,this._details?.origins.length??0);return l`<div class="dialog-actions">
          ${i}
          <button
            type="button"
            class="btn primary"
            aria-disabled=${this._busy||!n?"true":"false"}
            @click=${this._split}
          >
            ${o.splitConfirm}
          </button>
        </div>`}case"archive":return l`<div class="dialog-actions">
          ${i}
          <button
            type="button"
            class="btn primary danger"
            aria-disabled=${r}
            @click=${this._archive}
          >
            ${o.archive}
          </button>
        </div>`;default:{let n=(this._details?.origins.length??0)>=2;return l`<div class="dialog-actions" role="group" aria-label=${o.actions}>
          <button type="button" class="btn" data-mode="date" @click=${this._editDate}>
            ${o.editDate}
          </button>
          <button type="button" class="btn" data-mode="merge" @click=${this._startMerge}>
            ${o.mergeWith}
          </button>
          ${n?l`<button type="button" class="btn" data-mode="split" @click=${this._startSplit}>
                ${o.split}
              </button>`:c}
          ${e.archived?c:l`<button
                type="button"
                class="btn danger"
                data-mode="archive"
                @click=${this._startArchive}
              >
                ${o.archive}
              </button>`}
          ${Je(e.status)?l`<span class="spacer"></span>
                <button
                  type="button"
                  class="btn primary"
                  aria-disabled=${r}
                  @click=${this._markDelivered}
                >
                  <ha-icon icon="mdi:check" aria-hidden="true"></ha-icon>${o.markDelivered}
                </button>`:c}
        </div>`}}}_setMode(e){this._mode=e,this._error=null,this._formError=null,this.focusAfterRender(e==="archive"?"[data-cancel]":"[data-first], [data-cancel]")}_backToView(){let e=this._mode;this._mode="view",this._error=null,this._formError=null,this.focusAfterRender(`[data-mode="${e}"]`)}_editDate(){let e=this._parcel;this._dateForm=e?xr(e):Gr,this._setMode("date")}_startMerge(){this._mergeTarget="",this._setMode("merge")}_startSplit(){this._splitSelection=[],this._setMode("split")}_startArchive(){this._setMode("archive")}_parcelService(e,r,i){let n=this.hass,s=this._parcel;!n||!s||this.runAction(()=>V(n,e,{parcel_id:s.id,...r}),i)}_confirm(){this._parcelService("update",{confirm:!0})}_undoMerge(){this._parcelService("undo_merge",{})}_keepMerge(){this._parcelService("update",{confirm_merge:!0})}_markDelivered(){this._parcelService("mark_delivered",{})}_archive(){this._parcelService("archive",{},()=>this.closeDialog())}_onPrivateClick(e){this._busy&&e.preventDefault()}_togglePrivate(e){let r=e.currentTarget.checked,i=this.hass,n=this._parcel;!i||!n||this._busy||(this._pendingPrivate=r,this.runAction(async()=>{try{await V(i,"update",{parcel_id:n.id,private:r})}catch(s){throw this._pendingPrivate=null,s}}))}_onDateInput(e){let r=e.currentTarget,i=r.name;this._dateForm={...this._dateForm,[i]:r.value},this._formError=null}_saveDate(e){e.preventDefault();let r=this._parcel;if(!r||this._busy)return;let i=this._dateForm,n=je(i);if(n){this._formError=n,this.focusAfterRender(`[name="${n.field}"]`);return}let s=kr(r.id,i);this._parcelService("update",s,()=>this._backToView())}_resolvedMergeTarget(e){return e.some(r=>r.id===this._mergeTarget)?this._mergeTarget:e[0]?.id??""}_onMergeTarget(e){this._mergeTarget=e.currentTarget.value}_merge(){let e=this.hass,r=this._parcel;if(!e||!r)return;let i=this._resolvedMergeTarget(Qe(this.snapshot?.parcels??[],r.id));i&&this.runAction(()=>V(e,"merge",{parcel_ids:[r.id,i]}),()=>this._backToView())}_onSplitChange(e){let r=e.currentTarget,i=this._splitSelection.filter(n=>n!==r.value);this._splitSelection=r.checked?[...i,r.value]:i}_split(){let e=this._details?.origins.length??0;_t(this._splitSelection,e)&&this._parcelService("split",{origins:[...this._splitSelection]},()=>this._backToView())}async _copy(e){let r=e.currentTarget,i=this._parcel?.tracking_number?.trim();if(!i)return;this._copyState="idle";try{if(!navigator.clipboard?.writeText)throw new Error("Clipboard API unavailable");await navigator.clipboard.writeText(i),this._copyState="copied";return}catch{}let n=this.renderRoot.querySelector("#tracking-number");n?.focus(),n?.select();let s=!1;try{s=document.execCommand("copy")}catch{s=!1}this._copyState=s?"copied":"failed",s&&r.focus()}};I("parcels-details-dialog",St);var en="parcels/subscribe",Zr=[2e3,1e4,3e4,6e4,3e5],et=new Map,tn=0;function Qr(t,e){try{t(e)}catch(r){console.error(r)}}function Jr(t,e){t.state=e;for(let r of[...t.listeners.values()])Qr(r,e)}function Xr(t){try{t().catch(()=>{})}catch{}}function rt(t){t.retryTimer!==void 0&&(clearTimeout(t.retryTimer),t.retryTimer=void 0)}function tt(t){t.connection.removeEventListener("ready",t.onReady),t.connection.removeEventListener("disconnected",t.onDisconnected)}function rn(t){rt(t);let e=Zr[Math.min(t.retries,Zr.length-1)]??3e5;t.retries+=1,t.retryTimer=setTimeout(()=>{t.retryTimer=void 0,Tt(t)},e)}function Tt(t){if(t.released||t.unsubscribe||t.pending||t.listeners.size===0)return;rt(t);let e=++t.attempt,r=t.epoch,i=()=>!t.released&&t.attempt===e;t.pending=!0;let n;try{n=t.connection.subscribeMessage(s=>{i()&&(t.retries=0,Jr(t,{snapshot:Vr(s),error:null}))},{type:en},{resubscribe:!1})}catch(s){n=Promise.reject(s)}n.then(s=>{if(i()){t.pending=!1,t.unsubscribe=s;return}t.epoch===r&&Xr(s),t.released&&t.attempt===e+1&&(t.pending=!1,tt(t))},s=>{i()?(t.pending=!1,Jr(t,{snapshot:t.state.snapshot,error:R(s)}),rn(t)):t.released&&t.attempt===e+1&&(t.pending=!1,tt(t))})}function nn(t,e){if(!t.listeners.delete(e)||t.listeners.size>0)return;t.released=!0,t.attempt+=1,rt(t),et.get(t.connection)===t&&et.delete(t.connection);let r=t.unsubscribe;t.unsubscribe=null,r&&Xr(r),t.pending||tt(t)}function sn(t){let e={connection:t,listeners:new Map,state:{snapshot:null,error:null},epoch:0,attempt:0,unsubscribe:null,pending:!1,released:!1,retries:0,retryTimer:void 0,onReady:()=>{e.released||e.unsubscribe||(e.pending=!1,e.retries=0,Tt(e))},onDisconnected:()=>{e.epoch+=1,e.attempt+=1,e.unsubscribe=null,e.pending=!1,rt(e),e.released&&tt(e)}};return e}function ei(t,e){let r=++tn,i=et.get(t);i?(i.listeners.set(r,e),(i.state.snapshot||i.state.error)&&Qr(e,i.state)):(i=sn(t),et.set(t,i),i.listeners.set(r,e),t.addEventListener("ready",i.onReady),t.addEventListener("disconnected",i.onDisconnected),Tt(i));let n=i,s=!0;return()=>{s&&(s=!1,nn(n,r))}}var it=class{snapshot=null;error=null;_host;_connection=null;_unsubscribe=null;_hostConnected=!1;constructor(e){this._host=e,e.addController(this)}setConnection(e){e!==this._connection&&(this._release(),this._connection=e,this.snapshot=null,this.error=null,this._hostConnected&&this._subscribe(),this._host.requestUpdate())}hostConnected(){this._hostConnected=!0,this._subscribe()}hostDisconnected(){this._hostConnected=!1,this._release()}_subscribe(){!this._connection||this._unsubscribe||(this._unsubscribe=ei(this._connection,e=>{this.snapshot=e.snapshot??this.snapshot,this.error=e.error,this._host.requestUpdate()}))}_release(){let e=this._unsubscribe;this._unsubscribe=null,e?.()}};var Te=class extends E{static properties={_actionError:{state:!0}};_snapshots=new it(this);_hass=void 0;_hassKey=null;_locale=null;_localeKey="";constructor(){super(),this._actionError=null}get hass(){return this._hass}set hass(e){this._hass=e,this._snapshots.setConnection(e?.connection??null),this.toggleAttribute("dark",e?.themes?.darkMode===!0);let r=JSON.stringify([e?.language,e?.locale?.language,e?.locale?.time_format,e?.locale?.time_zone,e?.config?.time_zone,e?.user?.is_admin,e?.themes?.darkMode]);r!==this._hassKey&&(this._hassKey=r,this.requestUpdate()),this.hassChanged()}hassChanged(){}get snapshot(){return this._snapshots.snapshot}get locale(){let e=this._snapshots.snapshot?.settings.time_zone,r=`${this._hassKey??""}|${e??""}`;return(!this._locale||r!==this._localeKey)&&(this._locale=qe(this._hass,e),this._localeKey=r),this._locale}async callService(e,r,i){let n=this._hass;if(!n)return!1;this._actionError=null;try{return await V(n,e,r),!0}catch(s){return this._actionError=f(i,{message:R(s)}),!1}}renderBanners(){let{snapshot:e,error:r}=this._snapshots;return!r&&!this._actionError?c:l`<div class="banners">
      ${r?l`<div class="alert ${e?"warning":"error"}" role="alert">
            <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              ${f(e?o.refreshError:o.loadError,{message:r})}
            </span>
          </div>`:c}
      ${this._actionError?l`<div class="alert error" role="alert">
            <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
            <span class="grow">${this._actionError}</span>
            <button
              type="button"
              class="icon-btn"
              aria-label=${o.dismissMessage}
              title=${o.dismissMessage}
              @click=${this._dismissActionError}
            >
              <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
            </button>
          </div>`:c}
    </div>`}renderLoading(){return this._snapshots.error?c:l`<p class="empty" role="status">${o.loading}</p>`}showActionError(e){this._actionError=e}_dismissActionError(){this._actionError=null}},ue=class extends Te{static properties={_busyParcels:{state:!0}};_focusedParcel=null;constructor(){super(),this._busyParcels=new Set}willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement;this._focusedParcel=r instanceof HTMLElement?r.closest(".chip[data-parcel-id]")?.dataset.parcelId??null:null}updated(e){super.updated(e);let r=this._focusedParcel;this._focusedParcel=null,r!==null&&!this.shadowRoot?.activeElement&&Et()&&this.renderRoot.querySelector(xt(r))?.focus()}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback], button.chip-main")}openDetails=(e,r)=>{this.renderRoot.querySelector("parcels-details-dialog")?.open(e.id,()=>{(r.isConnected?r:this.renderRoot.querySelector(xt(e.id))??this.focusFallback())?.focus()})};undoMerge=e=>{this._parcelAction(e.id,"undo_merge",{parcel_id:e.id},o.undoFailed)};keepMerge=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_merge:!0},o.keepFailed)};renderDetailsDialog(){return l`<parcels-details-dialog
      .hass=${this.hass}
      .snapshot=${this.snapshot}
      .locale=${this.locale}
      @parcels-error=${this._onDialogError}
    ></parcels-details-dialog>`}async _parcelAction(e,r,i,n){if(!this._busyParcels.has(e)){this._busyParcels=new Set([...this._busyParcels,e]);try{await this.callService(r,i,n)}finally{let s=new Set(this._busyParcels);s.delete(e),this._busyParcels=s}}}_onDialogError(e){this.showActionError(e.detail)}};function Et(){let t=document.activeElement;return!t||t===document.body}function Ct(t){if(typeof t!="object"||t===null||Array.isArray(t))throw new Error(o.configInvalid);return t}function At(t){let e=t.title;if(e!=null){if(typeof e!="string")throw new Error(o.configTitle);return e.trim()}}function Rt(t){return typeof t.type=="string"?t.type:""}function Pt(t){let e=Ct(t),r=e.show_archived??!0;if(typeof r!="boolean")throw new Error(o.configShowArchived);return{type:Rt(e),title:At(e),show_archived:r}}function Mt(t){let e=Ct(t);return{type:Rt(e),title:At(e)}}function Dt(t){let e=Ct(t);return{type:Rt(e),title:At(e)}}function he(t,e){return t===void 0?e:t||null}function on(t,e){let r=$e(t.status_time,e.timeZone);switch(t.status){case"cancelled":return null;case"delivered":{let n=$e(t.delivered_at,e.timeZone)??r;return n?{kind:"delivered",from:n,to:n}:null}case"returned":return r?{kind:"returned",from:r,to:r}:null;case"ready_for_pickup":{let n=r??e.today;return{kind:"pickup",from:n,to:$r(n,e.today)}}default:break}let i=z(t);return i?{kind:"eta",from:i.start,to:i.end}:(t.status==="attempted"||t.status==="exception")&&r?{kind:"status",from:r,to:r}:null}function ti(t){return t.window_start??t.window_end??"~"}function Lt(t,e){return t<e?-1:t>e?1:0}function an(t,e){return t.startCol-e.startCol||e.endCol-e.startCol-(t.endCol-t.startCol)||Lt(ti(t.parcel),ti(e.parcel))||Lt(k(t.parcel).toLowerCase(),k(e.parcel).toLowerCase())||Lt(t.parcel.id,e.parcel.id)}function ri(t,e,r,i){let n=yr(e),s=oe(e,6),a=[];for(let u of t){if(u.archived&&!i.showArchived)continue;let m=on(u,r);!m||P(m.to,e)<0||P(m.from,s)>0||a.push({parcel:u,placement:m,startCol:Math.max(0,ft(e,m.from)),endCol:Math.min(6,ft(e,m.to)),continuesBefore:P(m.from,e)<0,continuesAfter:P(m.to,s)>0,lane:0})}a.sort(an);let p=[];for(let u of a){let m=p.findIndex(h=>h<u.startCol);m===-1&&(m=p.length),p[m]=u.endCol,u.lane=m}let d=n.map((u,m)=>a.filter(h=>h.startCol<=m&&m<=h.endCol).sort((h,g)=>h.lane-g.lane));return{start:e,end:s,days:n,items:a,lanes:p.length,perDay:d,busy:d.map(u=>u.length>0)}}var ln=600,dn=616,cn={weekday:"short"},pn={day:"numeric"},un={weekday:"long",day:"numeric",month:"long"},hn={weekday:"long",day:"numeric",month:"short"},It=class extends ue{static properties={_config:{state:!0},_weekOffset:{state:!0},_narrow:{state:!0},_refreshing:{state:!0}};static styles=[O,Ke,w`
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
    `];_resizeObserver=null;_resizeFrame=0;_layoutCache=null;constructor(){super(),this._config=Pt({}),this._weekOffset=0,this._narrow=!1,this._refreshing=!1}static getStubConfig(){return{}}setConfig(e){this._config=Pt(e)}getCardSize(){let e=this._layout();return e?this._narrow?9+e.perDay.reduce((i,n)=>i+n.length,0):3+Math.max(1,e.lanes):4}getGridOptions(){return{columns:"full",rows:"auto",min_columns:6}}connectedCallback(){super.connectedCallback(),typeof ResizeObserver<"u"&&(this._resizeObserver??=new ResizeObserver(e=>{let r=e[e.length-1]?.contentRect.width??0;cancelAnimationFrame(this._resizeFrame),this._resizeFrame=requestAnimationFrame(()=>this._measure(r))}),this._resizeObserver.observe(this))}disconnectedCallback(){super.disconnectedCallback(),this._resizeObserver?.disconnect(),cancelAnimationFrame(this._resizeFrame)}firstUpdated(e){super.firstUpdated(e),this._measure(this.getBoundingClientRect().width)}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback]")}_measure(e){e<=0||(e<ln?this._narrow=!0:e>=dn&&(this._narrow=!1))}_monday(e){return oe(vr(e.settings.today),7*this._weekOffset)}_layout(){let e=this.snapshot;if(!e)return null;let r=this._monday(e),i=this._config.show_archived,n=this._layoutCache;if(n&&n.snapshot===e&&n.monday===r&&n.showArchived===i)return n.layout;let s=ri(e.parcels,r,{today:e.settings.today,timeZone:e.settings.time_zone},{showArchived:i});return this._layoutCache={snapshot:e,monday:r,showArchived:i,layout:s},s}render(){let e=this.snapshot,r=this._layout(),i=he(this._config.title,o.defaultWeekTitle),n=r?F(r.start,r.end,this.locale,Pr):"";return l`<ha-card>
        <div class="header">
          <div class="heading">
            ${i?l`<h2 class="title">${i}</h2>`:c}
            ${n?l`<p class="range" aria-live="polite">${n}</p>`:c}
          </div>
          <div class="controls">
            <div class="nav" role="group" aria-label=${o.weekNavigation}>
              <button
                type="button"
                class="icon-btn"
                aria-label=${o.previousWeek}
                title=${o.previousWeek}
                @click=${this._previousWeek}
              >
                <ha-icon class="flip" icon="mdi:chevron-left" aria-hidden="true"></ha-icon>
              </button>
              <button type="button" class="btn" title=${o.goToToday} @click=${this._thisWeek}>
                ${o.today}
              </button>
              <button
                type="button"
                class="icon-btn"
                aria-label=${o.nextWeek}
                title=${o.nextWeek}
                @click=${this._nextWeek}
              >
                <ha-icon class="flip" icon="mdi:chevron-right" aria-hidden="true"></ha-icon>
              </button>
            </div>
            <button
              type="button"
              class="icon-btn"
              aria-label=${o.refresh}
              title=${o.refresh}
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
              <ha-icon icon="mdi:plus" aria-hidden="true"></ha-icon>${o.addParcel}
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
      ></parcels-add-dialog>`}_renderGrid(e,r,i){let n=this.locale,s=e.settings.today,a=r.items.length===0,d={"grid-template-columns":r.busy.map(u=>u||a?"minmax(0, 1fr)":"minmax(0, 0.6fr)").join(" "),"grid-template-rows":`auto repeat(${Math.max(1,r.lanes)}, auto)`};return l`<div
      class="grid"
      role="group"
      aria-label=${f(o.weekOf,{range:i})}
      style=${A(d)}
    >
      ${r.days.map((u,m)=>l`<div
            class="day-bg ${u===s?"today":""}"
            style=${A({"grid-column":String(m+1)})}
            aria-hidden="true"
          ></div>`)}
      ${r.days.map((u,m)=>l`<div
            class="day-head ${u===s?"today":""}"
            style=${A({"grid-column":String(m+1)})}
            aria-current=${u===s?"date":c}
          >
            <span class="dow" aria-hidden="true">${re(u,n,cn)}</span>
            <span class="dom" aria-hidden="true">${re(u,n,pn)}</span>
            <span class="sr-only">${re(u,n,un)}</span>
          </div>`)}
      ${a?l`<p class="week-empty">${o.noDeliveriesThisWeek}</p>`:c}
      ${K(r.items,u=>u.parcel.id,u=>this._chip(u,!1,{"grid-column":`${u.startCol+1} / ${u.endCol+2}`,"grid-row":String(u.lane+2)}))}
    </div>`}_renderStacked(e,r,i){let n=this.locale,s=e.settings.today;return l`<ol class="days" aria-label=${f(o.weekOf,{range:i})}>
      ${r.days.map((a,p)=>{let d=r.perDay[p]??[],u=a===s;return l`<li
          class="day ${d.length?"":"compact"} ${u?"today":""}"
          aria-current=${u?"date":c}
        >
          <p class="day-label">
            ${re(a,n,hn)}${u?l`<span class="badge info">${o.todayTag}</span>`:c}
          </p>
          ${d.length?l`<ul class="day-chips">
                ${K(d,m=>m.parcel.id,m=>l`<li>${this._chip(m,!0,void 0,p)}</li>`)}
              </ul>`:l`<span class="muted">${o.noDeliveriesThisDay}</span>`}
        </li>`})}
    </ol>`}_chip(e,r,i,n){let s=e.continuesBefore&&(!r||n===e.startCol),a=e.continuesAfter&&(!r||n===e.endCol);return Xe(e.parcel,{locale:this.locale,placement:e.placement,continuesBefore:s,continuesAfter:a,showRange:r,busy:this._busyParcels.has(e.parcel.id),position:i,onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge})}_previousWeek(){this._weekOffset-=1}_nextWeek(){this._weekOffset+=1}_thisWeek(){this._weekOffset=0}async _refresh(){if(!this._refreshing){this._refreshing=!0;try{await this.callService("refresh",{},o.refreshFailed)}finally{this._refreshing=!1}}}_openAdd(e){let r=e.currentTarget;this.renderRoot.querySelector("parcels-add-dialog")?.open(()=>{r.isConnected&&r.focus()})}_onAddError(e){this.showActionError(e.detail)}};I("parcels-week-card",It);ae("parcels-week-card",o.weekCardName,o.weekCardDescription);var Ot=class extends ue{static properties={_config:{state:!0}};static styles=[O,Ke,w`
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
    `];_listCache=null;constructor(){super(),this._config=Mt({})}static getStubConfig(){return{}}setConfig(e){this._config=Mt(e)}getCardSize(){let e=this._parcels();return e?1+Math.max(1,e.length):3}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}focusFallback(){return this.renderRoot.querySelector("button.chip-main")??this.renderRoot.querySelector(".content")}_parcels(){let e=this.snapshot;return e?(this._listCache?.snapshot!==e&&(this._listCache={snapshot:e,parcels:Ur(e.parcels)}),this._listCache.parcels):null}render(){let e=this._parcels(),r=he(this._config.title,o.defaultListTitle);return l`<ha-card>
        ${r?l`<div class="header"><h2 class="title">${r}</h2></div>`:c}
        ${this.renderBanners()}
        <div class="content" tabindex="-1">
          ${e?this._renderList(e):this.renderLoading()}
        </div>
      </ha-card>
      ${this.renderDetailsDialog()}`}_renderList(e){if(!e.length)return l`<p class="empty">${o.noUndatedParcels}</p>`;let r=this.locale;return l`<ul class="list">
      ${K(e,i=>i.id,i=>l`<li>
            ${Xe(i,{locale:r,showStatus:!0,busy:this._busyParcels.has(i.id),onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge})}
          </li>`)}
    </ul>`}};I("parcels-list-card",Ot);ae("parcels-list-card",o.listCardName,o.listCardDescription);var me=["review","filtered"],mn=new Set(["not_parcel","unknown"]),fn={weekday:"short",day:"numeric",month:"short"};function ii(t){return M(t.received??t.created)??-1/0}function ni(t){return[...t].sort((e,r)=>ii(r)-ii(e)||(e.id<r.id?-1:e.id>r.id?1:0))}function Ft(t,e){if(!t.has(e))return t;let r=new Map(t);return r.delete(e),r}var Nt=class extends Te{static properties={_config:{state:!0},_tab:{state:!0},_editing:{state:!0},_editForm:{state:!0},_editProblem:{state:!0},_busyItems:{state:!0},_itemErrors:{state:!0}};static styles=[O,w`
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
    `];connectedWhileHidden=!0;_focusedItem=null;_listCache=null;constructor(){super(),this._config=Dt({}),this._tab="review",this._editing=null,this._editForm=gt(null),this._editProblem=null,this._busyItems=new Set,this._itemErrors=new Map}static getStubConfig(){return{}}setConfig(e){this._config=Dt(e)}getCardSize(){if(!this._visible())return 0;let e=this._lists();if(!e)return 3;let r=this._tab==="review"?e.review.length:e.filtered.length;return 2+2*Math.max(1,r)}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}hassChanged(){this._syncVisibility()}_visible(){let e=this.snapshot;return e?e.settings.user_is_admin:this.hass?.user?.is_admin===!0}_syncVisibility(){let e=!this._visible();this.hidden!==e&&(this.hidden=e,this.dispatchEvent(new CustomEvent("card-visibility-changed",{bubbles:!0,composed:!0,detail:{value:!e}})))}_lists(){let e=this.snapshot;return e?(this._listCache?.snapshot!==e&&(this._listCache={snapshot:e,review:ni(e.review),filtered:ni(e.filtered)}),this._listCache):null}willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement,i=r instanceof HTMLElement?r.closest("[data-item-id]"):null;if(i){let s=[...this.renderRoot.querySelectorAll("[data-item-id]")].filter(a=>!a.closest("[hidden]"));this._focusedItem={id:i.dataset.itemId??"",index:s.indexOf(i)}}else this._focusedItem=null;let n=this._lists();if(n){let s=new Set([...n.review,...n.filtered].map(a=>a.id));this._editing!==null&&!s.has(this._editing)&&(this._editing=null,this._editProblem=null);for(let a of this._itemErrors.keys())s.has(a)||(this._itemErrors=Ft(this._itemErrors,a))}}updated(e){super.updated(e),this._syncVisibility();let r=this._focusedItem;if(this._focusedItem=null,!r||this.shadowRoot?.activeElement||!Et())return;let n=[...this.renderRoot.querySelector(`#panel-${this._tab}`)?.querySelectorAll("[data-item-id]")??[]];(n.find(a=>a.dataset.itemId===r.id)??n[Math.min(Math.max(r.index,0),n.length-1)]??this.renderRoot.querySelector(`#tab-${this._tab}`))?.focus()}render(){if(!this._visible())return c;let e=this._lists(),r=he(this._config.title,o.defaultReviewTitle);return l`<ha-card>
      ${r?l`<div class="header"><h2 class="title">${r}</h2></div>`:c}
      ${this.renderBanners()}
      ${e?l`${this._renderTabs(e.review.length,e.filtered.length)}
            <div
              class="panel"
              role="tabpanel"
              id="panel-review"
              aria-labelledby="tab-review"
              tabindex="0"
              ?hidden=${this._tab!=="review"}
            >
              ${this._renderReviewList(e.review)}
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
    </ha-card>`}_renderTabs(e,r){let i=n=>f(o.tabCount,{label:n==="review"?o.tabReview:o.tabFiltered,count:n==="review"?e:r});return l`<div
      class="tabs"
      role="tablist"
      aria-label=${o.reviewTabs}
      @keydown=${this._onTabKeyDown}
    >
      ${me.map(n=>{let s=this._tab===n;return l`<button
          type="button"
          class="tab"
          role="tab"
          id="tab-${n}"
          data-tab=${n}
          aria-selected=${s?"true":"false"}
          aria-controls="panel-${n}"
          tabindex=${s?"0":"-1"}
          @click=${this._onTabClick}
        >
          ${i(n)}
        </button>`})}
    </div>`}_renderReviewList(e){return e.length?l`<div class="items">
      ${K(e,r=>r.id,(r,i)=>this._renderReviewItem(r,i))}
    </div>`:l`<p class="empty">${o.emptyReview}</p>`}_renderFilteredList(e){return l`<p class="hint filtered-hint">${o.filteredHint}</p>
      ${e.length?l`<div class="items">
            ${K(e,r=>r.id,(r,i)=>this._renderFilteredItem(r,i))}
          </div>`:l`<p class="empty">${o.emptyFiltered}</p>`}`}_renderHead(e,r,i=c){return l`<div class="item-head">
        <span class="sender">${e.sender||e.sender_domain}</span>${i}
      </div>
      <h3 class="subject" id=${r}>${e.subject.trim()||o.noSubject}</h3>`}_renderError(e){let r=this._itemErrors.get(e);return r?l`<div class="alert error" role="alert">
          <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
          <span class="grow">${r}</span>
        </div>`:c}_renderReviewItem(e,r){let i=this.locale,n=this._busyItems.has(e.id),s=this._editing===e.id,a=`review-subject-${r}`,p=e.received??e.created,d=Dr(e.reason),u=[p?f(o.receivedOn,{date:B(p,i)}):"",e.mailbox_owner?f(o.mailboxOf,{owner:e.mailbox_owner}):"",d?f(o.reasonIs,{reason:d}):""].filter(Boolean),m=e.source==="ai"?l`<span class="badge ai" title=${o.aiSuggestionLabel}>
            ${o.aiBadge}<span class="sr-only">, ${o.aiSuggestionLabel}</span>
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
              <strong class="block">${o.unverifiedSender}</strong>
              ${o.unverifiedSenderHint}
            </span>
          </div>`}
      ${s?this._renderEditForm(e,n):this._renderSuggestion(e.suggestion)}
      ${this._renderError(e.id)} ${s?c:this._renderReviewActions(e,n)}
    </article>`}_renderSuggestion(e){if(!e)return l`<p class="hint section-label">${o.noSuggestion}</p>`;let r=this.locale,i=z(e),n=[[o.fieldKind,$t(e.kind)||null],[o.fieldMerchant,e.merchant],[o.fieldCarrier,de({carrier:e.carrier,carrier_name:null})],[o.fieldTrackingNumbers,e.tracking_numbers.join(", ")||null],[o.fieldOrderNumbers,e.order_numbers.join(", ")||null],[o.expected,i?F(i.start,i.end,r,fn):null],[o.timeWindow,le(e.window_start,e.window_end,r)],[o.pickupPoint,e.pickup_point],[o.pickupCode,e.pickup_code],[o.items,e.items.length?l`<ul>
              ${e.items.map(s=>l`<li>${s}</li>`)}
            </ul>`:null]];return l`<p class="section-label">${o.suggestion}</p>
      <dl class="facts">
        ${n.filter(([,s])=>s!==null&&s!=="").map(([s,a])=>l`<dt>${s}</dt><dd>${a}</dd>`)}
      </dl>`}_renderReviewActions(e,r){let i=r?"true":"false",n=e.sender_domain||e.sender;return l`<div class="row-actions">
      ${e.suggestion?l`<button
            type="button"
            class="btn primary"
            aria-disabled=${i}
            @click=${()=>this._accept(e)}
          >
            ${o.accept}
          </button>`:c}
      <button
        type="button"
        class="btn"
        data-edit
        aria-disabled=${i}
        @click=${()=>this._startEdit(e)}
      >
        ${o.edit}
      </button>
      <button
        type="button"
        class="btn"
        aria-disabled=${i}
        @click=${()=>this._command(e.id,"review/dismiss",{review_id:e.id})}
      >
        ${o.dismiss}
      </button>
      <button
        type="button"
        class="btn"
        title=${f(o.trustSenderHint,{domain:n})}
        aria-disabled=${i}
        @click=${()=>this._command(e.id,"review/trust_sender",{review_id:e.id})}
      >
        ${o.trustSender}
      </button>
      <button
        type="button"
        class="btn danger"
        title=${f(o.ignoreSenderHint,{domain:n})}
        aria-disabled=${i}
        @click=${()=>this._command(e.id,"review/ignore_sender",{review_id:e.id})}
      >
        ${o.ignoreSender}
      </button>
    </div>`}_renderEditForm(e,r){let i=this._editForm,n=this._editProblem,s=Object.keys(Ue).filter(d=>!mn.has(d)||d===i.kind);s.includes(i.kind)||s.unshift(i.kind);let a=He();i.carrier&&!Object.hasOwn(Y,i.carrier)&&a.unshift({id:i.carrier,name:i.carrier});let p=(d,u,m="text",h)=>{let g=n?.field===d,_=[g?"edit-error":"",h??""].filter(Boolean).join(" ");return l`<label class="field">
        <span class="field-label">${u}</span>
        <input
          type=${m}
          name=${d}
          autocomplete="off"
          .value=${S(i[d])}
          aria-invalid=${g?"true":"false"}
          aria-describedby=${_||c}
          @input=${this._onEditInput}
        />
      </label>`};return l`<form id="edit-form" class="edit-form" novalidate @submit=${this._submitEdit}>
      <div class="form-grid">
        <label class="field">
          <span class="field-label">${o.fieldKind}</span>
          <select name="kind" data-first @change=${this._onEditInput}>
            ${s.map(d=>l`<option value=${d} ?selected=${d===i.kind}>
                  ${$t(d)||d}
                </option>`)}
          </select>
        </label>
        ${p("merchant",o.fieldMerchant)}
        <label class="field">
          <span class="field-label">${o.fieldCarrier}</span>
          <select name="carrier" @change=${this._onEditInput}>
            <option value="" ?selected=${i.carrier===""}>${o.carrierUnknown}</option>
            ${a.map(d=>l`<option value=${d.id} ?selected=${d.id===i.carrier}>
                  ${d.name}
                </option>`)}
          </select>
        </label>
        <div class="field">
          ${p("tracking_numbers",o.fieldTrackingNumbers,"text","edit-hint-tracking")}
          <p class="hint" id="edit-hint-tracking">${o.hintList}</p>
        </div>
        <div class="field">
          ${p("order_numbers",o.fieldOrderNumbers,"text","edit-hint-orders")}
          <p class="hint" id="edit-hint-orders">${o.hintList}</p>
        </div>
        ${p("eta_start",o.fieldEtaStart,"date")}
        ${p("eta_end",o.fieldEtaEnd,"date")}
        ${p("window_start",o.fieldWindowStart,"time")}
        ${p("window_end",o.fieldWindowEnd,"time")}
        ${p("pickup_point",o.fieldPickupPoint)}
        ${p("pickup_code",o.fieldPickupCode)}
        <label class="field wide">
          <span class="field-label">${o.fieldItems}</span>
          <textarea
            name="items"
            rows="3"
            .value=${S(i.items)}
            aria-describedby="edit-hint-items"
            @input=${this._onEditInput}
          ></textarea>
          <span class="hint" id="edit-hint-items">${o.hintItems}</span>
        </label>
      </div>
      ${n?l`<div class="alert error" id="edit-error" role="alert">
            <span class="grow">${n.message}</span>
          </div>`:c}
      <div class="row-actions">
        <button type="submit" class="btn primary" aria-disabled=${r?"true":"false"}>
          ${o.acceptWithChanges}
        </button>
        <button type="button" class="btn" @click=${()=>this._cancelEdit(e.id)}>
          ${o.cancel}
        </button>
      </div>
    </form>`}_renderFilteredItem(e,r){let i=`filtered-subject-${r}`,n=e.received??e.created,s=this._busyItems.has(e.id);return l`<article
      class="item"
      tabindex="-1"
      data-item-id=${e.id}
      aria-labelledby=${i}
      aria-busy=${s?"true":"false"}
    >
      ${this._renderHead(e,i)}
      ${n?l`<p class="meta">
            ${f(o.receivedOn,{date:B(n,this.locale)})}
          </p>`:c}
      ${this._renderError(e.id)}
      <div class="row-actions">
        <button
          type="button"
          class="btn"
          aria-disabled=${s?"true":"false"}
          @click=${()=>this._command(e.id,"review/restore",{filtered_id:e.id})}
        >
          ${o.restore}
        </button>
      </div>
    </article>`}_selectTab(e,r){this._tab=e,r&&this.updateComplete.then(()=>this.renderRoot.querySelector(`#tab-${e}`)?.focus())}_onTabClick(e){let r=e.currentTarget.dataset.tab;this._selectTab(r,!1)}_onTabKeyDown(e){let r=me.indexOf(this._tab),i=getComputedStyle(e.currentTarget).direction==="rtl",n;switch(e.key){case"ArrowRight":n=r+(i?-1:1);break;case"ArrowLeft":n=r+(i?1:-1);break;case"Home":n=0;break;case"End":n=me.length-1;break;default:return}e.preventDefault();let s=me[(n+me.length)%me.length];s&&this._selectTab(s,!0)}_focusInItem(e,r){this.updateComplete.then(()=>{let i=this.renderRoot.querySelector(`[data-item-id="${CSS.escape(e)}"]`);(i?.querySelector(r)??i)?.focus()})}_startEdit(e){this._busyItems.has(e.id)||(this._editing=e.id,this._editForm=gt(e.suggestion),this._editProblem=null,this._itemErrors=Ft(this._itemErrors,e.id),this._focusInItem(e.id,"[data-first]"))}_cancelEdit(e){this._editing=null,this._editProblem=null,this._focusInItem(e,"[data-edit]")}_onEditInput(e){let r=e.currentTarget,i=r.name;this._editForm={...this._editForm,[i]:r.value},this._editProblem=null}_submitEdit(e){e.preventDefault();let r=this._editing;if(r===null||this._busyItems.has(r))return;let i=je(this._editForm);if(i){this._editProblem=i,this._focusInItem(r,`[name="${i.field}"]`);return}this._command(r,"review/accept",{review_id:r,overrides:Tr(this._editForm)},()=>{this._editing===r&&(this._editing=null)})}_accept(e){this._command(e.id,"review/accept",{review_id:e.id})}async _command(e,r,i,n){let s=this.hass;if(!(!s||this._busyItems.has(e))){this._busyItems=new Set([...this._busyItems,e]),this._itemErrors=Ft(this._itemErrors,e);try{await Ne(s,r,i),n?.()}catch(a){let p=f(o.actionFailed,{message:R(a)}),d=this._lists();[...d?.review??[],...d?.filtered??[]].some(m=>m.id===e)?this._itemErrors=new Map([...this._itemErrors,[e,p]]):this.showActionError(p)}finally{let a=new Set(this._busyItems);a.delete(e),this._busyItems=a}}}};I("parcels-review-card",Nt);ae("parcels-review-card",o.reviewCardName,o.reviewCardDescription);
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
