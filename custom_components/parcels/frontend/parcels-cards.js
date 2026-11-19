var Ne=globalThis,He=Ne.ShadowRoot&&(Ne.ShadyCSS===void 0||Ne.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,xt=Symbol(),mr=new WeakMap,ke=class{constructor(e,r,i){if(this._$cssResult$=!0,i!==xt)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=r}get styleSheet(){let e=this.o,r=this.t;if(He&&e===void 0){let i=r!==void 0&&r.length===1;i&&(e=mr.get(r)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&mr.set(r,e))}return e}toString(){return this.cssText}},fr=t=>new ke(typeof t=="string"?t:t+"",void 0,xt),x=(t,...e)=>{let r=t.length===1?t[0]:e.reduce((i,n,o)=>i+(a=>{if(a._$cssResult$===!0)return a.cssText;if(typeof a=="number")return a;throw Error("Value passed to 'css' function must be a 'css' function result: "+a+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(n)+t[o+1],t[0]);return new ke(r,t,xt)},gr=(t,e)=>{if(He)t.adoptedStyleSheets=e.map(r=>r instanceof CSSStyleSheet?r:r.styleSheet);else for(let r of e){let i=document.createElement("style"),n=Ne.litNonce;n!==void 0&&i.setAttribute("nonce",n),i.textContent=r.cssText,t.appendChild(i)}},kt=He?t=>t:t=>t instanceof CSSStyleSheet?(e=>{let r="";for(let i of e.cssRules)r+=i.cssText;return fr(r)})(t):t;var{is:rn,defineProperty:nn,getOwnPropertyDescriptor:sn,getOwnPropertyNames:on,getOwnPropertySymbols:an,getPrototypeOf:ln}=Object,Ue=globalThis,_r=Ue.trustedTypes,dn=_r?_r.emptyScript:"",cn=Ue.reactiveElementPolyfillSupport,Se=(t,e)=>t,St={toAttribute(t,e){switch(e){case Boolean:t=t?dn:null;break;case Object:case Array:t=t==null?t:JSON.stringify(t)}return t},fromAttribute(t,e){let r=t;switch(e){case Boolean:r=t!==null;break;case Number:r=t===null?null:Number(t);break;case Object:case Array:try{r=JSON.parse(t)}catch{r=null}}return r}},vr=(t,e)=>!rn(t,e),br={attribute:!0,type:String,converter:St,reflect:!1,useDefault:!1,hasChanged:vr};Symbol.metadata??=Symbol("metadata"),Ue.litPropertyMetadata??=new WeakMap;var K=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,r=br){if(r.state&&(r.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((r=Object.create(r)).wrapped=!0),this.elementProperties.set(e,r),!r.noAccessor){let i=Symbol(),n=this.getPropertyDescriptor(e,i,r);n!==void 0&&nn(this.prototype,e,n)}}static getPropertyDescriptor(e,r,i){let{get:n,set:o}=sn(this.prototype,e)??{get(){return this[r]},set(a){this[r]=a}};return{get:n,set(a){let d=n?.call(this);o?.call(this,a),this.requestUpdate(e,d,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??br}static _$Ei(){if(this.hasOwnProperty(Se("elementProperties")))return;let e=ln(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(Se("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(Se("properties"))){let r=this.properties,i=[...on(r),...an(r)];for(let n of i)this.createProperty(n,r[n])}let e=this[Symbol.metadata];if(e!==null){let r=litPropertyMetadata.get(e);if(r!==void 0)for(let[i,n]of r)this.elementProperties.set(i,n)}this._$Eh=new Map;for(let[r,i]of this.elementProperties){let n=this._$Eu(r,i);n!==void 0&&this._$Eh.set(n,r)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let r=[];if(Array.isArray(e)){let i=new Set(e.flat(1/0).reverse());for(let n of i)r.unshift(kt(n))}else e!==void 0&&r.push(kt(e));return r}static _$Eu(e,r){let i=r.attribute;return i===!1?void 0:typeof i=="string"?i:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,r=this.constructor.elementProperties;for(let i of r.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return gr(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,r,i){this._$AK(e,i)}_$ET(e,r){let i=this.constructor.elementProperties.get(e),n=this.constructor._$Eu(e,i);if(n!==void 0&&i.reflect===!0){let o=(i.converter?.toAttribute!==void 0?i.converter:St).toAttribute(r,i.type);this._$Em=e,o==null?this.removeAttribute(n):this.setAttribute(n,o),this._$Em=null}}_$AK(e,r){let i=this.constructor,n=i._$Eh.get(e);if(n!==void 0&&this._$Em!==n){let o=i.getPropertyOptions(n),a=typeof o.converter=="function"?{fromAttribute:o.converter}:o.converter?.fromAttribute!==void 0?o.converter:St;this._$Em=n;let d=a.fromAttribute(r,o.type);this[n]=d??this._$Ej?.get(n)??d,this._$Em=null}}requestUpdate(e,r,i,n=!1,o){if(e!==void 0){let a=this.constructor;if(n===!1&&(o=this[e]),i??=a.getPropertyOptions(e),!((i.hasChanged??vr)(o,r)||i.useDefault&&i.reflect&&o===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,i))))return;this.C(e,r,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,r,{useDefault:i,reflect:n,wrapped:o},a){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??r??this[e]),o!==!0||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||i||(r=void 0),this._$AL.set(e,r)),n===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(r){Promise.reject(r)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[n,o]of this._$Ep)this[n]=o;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[n,o]of i){let{wrapped:a}=o,d=this[n];a!==!0||this._$AL.has(n)||d===void 0||this.C(n,void 0,o,d)}}let e=!1,r=this._$AL;try{e=this.shouldUpdate(r),e?(this.willUpdate(r),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(r)):this._$EM()}catch(i){throw e=!1,this._$EM(),i}e&&this._$AE(r)}willUpdate(e){}_$AE(e){this._$EO?.forEach(r=>r.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(r=>this._$ET(r,this[r])),this._$EM()}updated(e){}firstUpdated(e){}};K.elementStyles=[],K.shadowRootOptions={mode:"open"},K[Se("elementProperties")]=new Map,K[Se("finalized")]=new Map,cn?.({ReactiveElement:K}),(Ue.reactiveElementVersions??=[]).push("2.1.2");var At=globalThis,yr=t=>t,Be=At.trustedTypes,$r=Be?Be.createPolicy("lit-html",{createHTML:t=>t}):void 0,Ct="$lit$",W=`lit$${Math.random().toFixed(9).slice(2)}$`,Et="?"+W,un=`<${Et}>`,ae=document,Ae=()=>ae.createComment(""),Ce=t=>t===null||typeof t!="object"&&typeof t!="function",Pt=Array.isArray,Ar=t=>Pt(t)||typeof t?.[Symbol.iterator]=="function",Tt=`[ 	
\f\r]`,Te=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,wr=/-->/g,xr=/>/g,se=RegExp(`>|${Tt}(?:([^\\s"'>=/]+)(${Tt}*=${Tt}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),kr=/'/g,Sr=/"/g,Cr=/^(?:script|style|textarea|title)$/i,Rt=t=>(e,...r)=>({_$litType$:t,strings:e,values:r}),l=Rt(1),Fs=Rt(2),Ns=Rt(3),$=Symbol.for("lit-noChange"),u=Symbol.for("lit-nothing"),Tr=new WeakMap,oe=ae.createTreeWalker(ae,129);function Er(t,e){if(!Pt(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return $r!==void 0?$r.createHTML(e):e}var Pr=(t,e)=>{let r=t.length-1,i=[],n,o=e===2?"<svg>":e===3?"<math>":"",a=Te;for(let d=0;d<r;d++){let c=t[d],h,f,p=-1,g=0;for(;g<c.length&&(a.lastIndex=g,f=a.exec(c),f!==null);)g=a.lastIndex,a===Te?f[1]==="!--"?a=wr:f[1]!==void 0?a=xr:f[2]!==void 0?(Cr.test(f[2])&&(n=RegExp("</"+f[2],"g")),a=se):f[3]!==void 0&&(a=se):a===se?f[0]===">"?(a=n??Te,p=-1):f[1]===void 0?p=-2:(p=a.lastIndex-f[2].length,h=f[1],a=f[3]===void 0?se:f[3]==='"'?Sr:kr):a===Sr||a===kr?a=se:a===wr||a===xr?a=Te:(a=se,n=void 0);let _=a===se&&t[d+1].startsWith("/>")?" ":"";o+=a===Te?c+un:p>=0?(i.push(h),c.slice(0,p)+Ct+c.slice(p)+W+_):c+W+(p===-2?d:_)}return[Er(t,o+(t[r]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),i]},Ee=class t{constructor({strings:e,_$litType$:r},i){let n;this.parts=[];let o=0,a=0,d=e.length-1,c=this.parts,[h,f]=Pr(e,r);if(this.el=t.createElement(h,i),oe.currentNode=this.el.content,r===2||r===3){let p=this.el.content.firstChild;p.replaceWith(...p.childNodes)}for(;(n=oe.nextNode())!==null&&c.length<d;){if(n.nodeType===1){if(n.hasAttributes())for(let p of n.getAttributeNames())if(p.endsWith(Ct)){let g=f[a++],_=n.getAttribute(p).split(W),b=/([.?@])?(.*)/.exec(g);c.push({type:1,index:o,name:b[2],strings:_,ctor:b[1]==="."?je:b[1]==="?"?Ke:b[1]==="@"?We:de}),n.removeAttribute(p)}else p.startsWith(W)&&(c.push({type:6,index:o}),n.removeAttribute(p));if(Cr.test(n.tagName)){let p=n.textContent.split(W),g=p.length-1;if(g>0){n.textContent=Be?Be.emptyScript:"";for(let _=0;_<g;_++)n.append(p[_],Ae()),oe.nextNode(),c.push({type:2,index:++o});n.append(p[g],Ae())}}}else if(n.nodeType===8)if(n.data===Et)c.push({type:2,index:o});else{let p=-1;for(;(p=n.data.indexOf(W,p+1))!==-1;)c.push({type:7,index:o}),p+=W.length-1}o++}}static createElement(e,r){let i=ae.createElement("template");return i.innerHTML=e,i}};function le(t,e,r=t,i){if(e===$)return e;let n=i!==void 0?r._$Co?.[i]:r._$Cl,o=Ce(e)?void 0:e._$litDirective$;return n?.constructor!==o&&(n?._$AO?.(!1),o===void 0?n=void 0:(n=new o(t),n._$AT(t,r,i)),i!==void 0?(r._$Co??=[])[i]=n:r._$Cl=n),n!==void 0&&(e=le(t,n._$AS(t,e.values),n,i)),e}var ze=class{constructor(e,r){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=r}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:r},parts:i}=this._$AD,n=(e?.creationScope??ae).importNode(r,!0);oe.currentNode=n;let o=oe.nextNode(),a=0,d=0,c=i[0];for(;c!==void 0;){if(a===c.index){let h;c.type===2?h=new me(o,o.nextSibling,this,e):c.type===1?h=new c.ctor(o,c.name,c.strings,this,e):c.type===6&&(h=new qe(o,this,e)),this._$AV.push(h),c=i[++d]}a!==c?.index&&(o=oe.nextNode(),a++)}return oe.currentNode=ae,n}p(e){let r=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(e,i,r),r+=i.strings.length-2):i._$AI(e[r])),r++}},me=class t{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,r,i,n){this.type=2,this._$AH=u,this._$AN=void 0,this._$AA=e,this._$AB=r,this._$AM=i,this.options=n,this._$Cv=n?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,r=this._$AM;return r!==void 0&&e?.nodeType===11&&(e=r.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,r=this){e=le(this,e,r),Ce(e)?e===u||e==null||e===""?(this._$AH!==u&&this._$AR(),this._$AH=u):e!==this._$AH&&e!==$&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):Ar(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==u&&Ce(this._$AH)?this._$AA.nextSibling.data=e:this.T(ae.createTextNode(e)),this._$AH=e}$(e){let{values:r,_$litType$:i}=e,n=typeof i=="number"?this._$AC(e):(i.el===void 0&&(i.el=Ee.createElement(Er(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===n)this._$AH.p(r);else{let o=new ze(n,this),a=o.u(this.options);o.p(r),this.T(a),this._$AH=o}}_$AC(e){let r=Tr.get(e.strings);return r===void 0&&Tr.set(e.strings,r=new Ee(e)),r}k(e){Pt(this._$AH)||(this._$AH=[],this._$AR());let r=this._$AH,i,n=0;for(let o of e)n===r.length?r.push(i=new t(this.O(Ae()),this.O(Ae()),this,this.options)):i=r[n],i._$AI(o),n++;n<r.length&&(this._$AR(i&&i._$AB.nextSibling,n),r.length=n)}_$AR(e=this._$AA.nextSibling,r){for(this._$AP?.(!1,!0,r);e!==this._$AB;){let i=yr(e).nextSibling;yr(e).remove(),e=i}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},de=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,r,i,n,o){this.type=1,this._$AH=u,this._$AN=void 0,this.element=e,this.name=r,this._$AM=n,this.options=o,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=u}_$AI(e,r=this,i,n){let o=this.strings,a=!1;if(o===void 0)e=le(this,e,r,0),a=!Ce(e)||e!==this._$AH&&e!==$,a&&(this._$AH=e);else{let d=e,c,h;for(e=o[0],c=0;c<o.length-1;c++)h=le(this,d[i+c],r,c),h===$&&(h=this._$AH[c]),a||=!Ce(h)||h!==this._$AH[c],h===u?e=u:e!==u&&(e+=(h??"")+o[c+1]),this._$AH[c]=h}a&&!n&&this.j(e)}j(e){e===u?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},je=class extends de{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===u?void 0:e}},Ke=class extends de{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==u)}},We=class extends de{constructor(e,r,i,n,o){super(e,r,i,n,o),this.type=5}_$AI(e,r=this){if((e=le(this,e,r,0)??u)===$)return;let i=this._$AH,n=e===u&&i!==u||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,o=e!==u&&(i===u||n);n&&this.element.removeEventListener(this.name,this,i),o&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},qe=class{constructor(e,r,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=r,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){le(this,e)}},Rr={M:Ct,P:W,A:Et,C:1,L:Pr,R:ze,D:Ar,V:le,I:me,H:de,N:Ke,U:We,B:je,F:qe},pn=At.litHtmlPolyfillSupport;pn?.(Ee,me),(At.litHtmlVersions??=[]).push("3.3.3");var Mr=(t,e,r)=>{let i=r?.renderBefore??e,n=i._$litPart$;if(n===void 0){let o=r?.renderBefore??null;i._$litPart$=n=new me(e.insertBefore(Ae(),o),o,void 0,r??{})}return n._$AI(t),n};var Mt=globalThis,D=class extends K{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let r=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Mr(r,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return $}};D._$litElement$=!0,D.finalized=!0,Mt.litElementHydrateSupport?.({LitElement:D});var hn=Mt.litElementPolyfillSupport;hn?.({LitElement:D});(Mt.litElementVersions??=[]).push("4.2.2");var A={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},V=t=>(...e)=>({_$litDirective$:t,values:e}),O=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,r,i){this._$Ct=e,this._$AM=r,this._$Ci=i}_$AS(e,r){return this.update(e,r)}update(e,r){return this.render(...r)}};var{I:mn}=Rr,Ir=t=>t;var Dr=t=>t.strings===void 0,Lr=()=>document.createComment(""),fe=(t,e,r)=>{let i=t._$AA.parentNode,n=e===void 0?t._$AB:e._$AA;if(r===void 0){let o=i.insertBefore(Lr(),n),a=i.insertBefore(Lr(),n);r=new mn(o,a,t,t.options)}else{let o=r._$AB.nextSibling,a=r._$AM,d=a!==t;if(d){let c;r._$AQ?.(t),r._$AM=t,r._$AP!==void 0&&(c=t._$AU)!==a._$AU&&r._$AP(c)}if(o!==n||d){let c=r._$AA;for(;c!==o;){let h=Ir(c).nextSibling;Ir(i).insertBefore(c,n),c=h}}}return r},Q=(t,e,r=t)=>(t._$AI(e,r),t),fn={},Ye=(t,e=fn)=>t._$AH=e,Or=t=>t._$AH,Ge=t=>{t._$AR(),t._$AA.remove()};var Fr=(t,e,r)=>{let i=new Map;for(let n=e;n<=r;n++)i.set(t[n],n);return i},q=V(class extends O{constructor(t){if(super(t),t.type!==A.CHILD)throw Error("repeat() can only be used in text expressions")}dt(t,e,r){let i;r===void 0?r=e:e!==void 0&&(i=e);let n=[],o=[],a=0;for(let d of t)n[a]=i?i(d,a):a,o[a]=r(d,a),a++;return{values:o,keys:n}}render(t,e,r){return this.dt(t,e,r).values}update(t,[e,r,i]){let n=Or(t),{values:o,keys:a}=this.dt(e,r,i);if(!Array.isArray(n))return this.ut=a,o;let d=this.ut??=[],c=[],h,f,p=0,g=n.length-1,_=0,b=o.length-1;for(;p<=g&&_<=b;)if(n[p]===null)p++;else if(n[g]===null)g--;else if(d[p]===a[_])c[_]=Q(n[p],o[_]),p++,_++;else if(d[g]===a[b])c[b]=Q(n[g],o[b]),g--,b--;else if(d[p]===a[b])c[b]=Q(n[p],o[b]),fe(t,c[b+1],n[p]),p++,b--;else if(d[g]===a[_])c[_]=Q(n[g],o[_]),fe(t,n[p],n[g]),g--,_++;else if(h===void 0&&(h=Fr(a,_,b),f=Fr(d,p,g)),h.has(d[p]))if(h.has(d[g])){let S=f.get(a[_]),T=S!==void 0?n[S]:null;if(T===null){let xe=fe(t,n[p]);Q(xe,o[_]),c[_]=xe}else c[_]=Q(T,o[_]),fe(t,n[p],T),n[S]=null;_++}else Ge(n[g]),g--;else Ge(n[p]),p++;for(;_<=b;){let S=fe(t,c[b+1]);Q(S,o[_]),c[_++]=S}for(;p<=g;){let S=n[p++];S!==null&&Ge(S)}return this.ut=a,Ye(t,c),$}});var Nr="important",gn=" !"+Nr,F=V(class extends O{constructor(t){if(super(t),t.type!==A.ATTRIBUTE||t.name!=="style"||t.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(t){return Object.keys(t).reduce((e,r)=>{let i=t[r];return i==null?e:e+`${r=r.includes("-")?r:r.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${i};`},"")}update(t,[e]){let{style:r}=t.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(e)),this.render(e);for(let i of this.ft)e[i]==null&&(this.ft.delete(i),i.includes("-")?r.removeProperty(i):r[i]=null);for(let i in e){let n=e[i];if(n!=null){this.ft.add(i);let o=typeof n=="string"&&n.endsWith(gn);i.includes("-")||o?r.setProperty(i,o?n.slice(0,-11):n,o?Nr:""):r[i]=n}}return $}});var C=V(class extends O{constructor(t){if(super(t),t.type!==A.PROPERTY&&t.type!==A.ATTRIBUTE&&t.type!==A.BOOLEAN_ATTRIBUTE)throw Error("The `live` directive is not allowed on child or event bindings");if(!Dr(t))throw Error("`live` bindings can only contain a single expression")}render(t){return t}update(t,[e]){if(e===$||e===u)return e;let r=t.element,i=t.name;if(t.type===A.PROPERTY){if(e===r[i])return $}else if(t.type===A.BOOLEAN_ATTRIBUTE){if(!!e===r.hasAttribute(i))return $}else if(t.type===A.ATTRIBUTE&&r.getAttribute(i)===e+"")return $;return Ye(t),e}});var Hr="parcels";function Z(t,e,r){return t.callService(Hr,e,r,void 0,!1)}function J(t,e,r={}){return t.callWS({...r,type:`${Hr}/${e}`})}var X={amazon:"Amazon Logistics",asendia:"Asendia",bpost:"bpost",brt:"BRT",cainiao:"Cainiao",chronopost:"Chronopost",colissimo:"Colissimo",correos:"Correos",correos_express:"Correos Express",ctt:"CTT",ctt_expresso:"CTT Expresso",deutsche_post:"Deutsche Post",dhl:"DHL",dpd:"DPD",evri:"Evri",fedex:"FedEx",gls:"GLS",hermes:"Hermes",inpost:"InPost",la_poste:"La Poste",mondial_relay:"Mondial Relay",mrw:"MRW",nacex:"Nacex",paack:"Paack",postnl:"PostNL",poste_italiane:"Poste Italiane",royal_mail:"Royal Mail",sda:"SDA",seur:"SEUR",tnt:"TNT",ups:"UPS",usps:"USPS",vinted_go:"Vinted Go",yunexpress:"YunExpress",other:"Other"};function Ve(){return Object.entries(X).filter(([t])=>t!=="other").map(([t,e])=>({id:t,name:e})).sort((t,e)=>t.name.localeCompare(e.name,"en",{sensitivity:"base"})).concat([{id:"other",name:X.other??"Other"}])}function Ur(t){return Object.hasOwn(X,t)?X[t]??t:t}var s={weekCardName:"Parcels week",weekCardDescription:"A Monday to Sunday calendar of your parcel deliveries.",listCardName:"Parcels without a date",listCardDescription:"Active parcels that don't have a delivery date yet.",reviewCardName:"Parcels review",reviewCardDescription:"E-mails that need a decision before Parcels uses them. Only shown to administrators.",defaultWeekTitle:"Parcels",defaultListTitle:"No date yet",defaultReviewTitle:"Parcels review",loading:"Loading parcels\u2026",loadError:"Couldn't load parcels: {message}",refreshError:"Couldn't update parcels: {message}",unknownError:"Unknown error",close:"Close",cancel:"Cancel",save:"Save",dismissMessage:"Dismiss message",configInvalid:"Invalid configuration: expected a map of options.",configTitle:'Invalid configuration: "title" must be text.',configShowArchived:'Invalid configuration: "show_archived" must be true or false.',previousWeek:"Previous week",nextWeek:"Next week",today:"Today",goToToday:"Go to the current week",weekNavigation:"Week navigation",weekOf:"Week of {range}",refresh:"Check mailboxes now",refreshFailed:"Couldn't check the mailboxes: {message}",addParcel:"Add parcel",noDeliveriesThisWeek:"No deliveries this week",noDeliveriesThisDay:"No deliveries",filterLabel:"Show parcels",filterAll:"All",filterActive:"Active",filterRecent:"Recent",filterRecentHint:"Changed or expected this week",filterCompleted:"Completed",filterEmptyWeek:"Nothing to show this week with this filter",filterNote:"Filter: {filter}",filterShowAll:"Show all",todayTag:"Today",privateParcel:"Private parcel",unnamedParcel:"Parcel",packages:"{count} packages",carrierNotKnown:"Carrier not known yet",carrierNotKnownLabel:"carrier not known yet",carrierIs:"carrier {carrier}",hasCode:"PIN in the details",pin:"PIN {code}",unknownSeller:"Unknown seller",itemsCount:"{count} items",itemsNotKnown:"Items not known yet",possibly:"Possibly: {items}",possiblyOr:" or ",itemsMore:"{name} +{count}",possibleMatches:"Possibly the same package as",possibleMatchesHint:"Not confirmed: this package's e-mails don't name the order. Merge the parcel it is, or rule one out.",notThisOne:"Not this one",notThisOneLabel:"{candidate} isn't {title}",aiBadge:"AI",aiBadgeLabel:"found by the local AI",aiFilledLabel:"details filled in by the local AI",privateLabel:"private",autoMerged:"Auto-merged \u2014 check",autoMergedLabel:"merged automatically, please check",undo:"Undo",undoMergeLabel:"Undo the automatic merge of {title}",undoFailed:"Couldn't undo the merge: {message}",keep:"Keep",keepMergeLabel:"Keep the automatic merge of {title}",keepFailed:"Couldn't keep the merge: {message}",inferred:"Delivery inferred \u2014 check",inferredLabel:"delivery inferred, please check",undoInferredLabel:"Undo the inferred delivery of {title}",undoInferredFailed:"Couldn't undo the delivery: {message}",keepInferredLabel:"Keep the inferred delivery of {title}",keepInferredFailed:"Couldn't keep the delivery: {message}",continuesBefore:"started before this week",continuesAfter:"continues after this week",deliveredOn:"delivered {date}",returnedOn:"returned {date}",expectedOn:"expected {date}",readyForPickupSince:"ready for pickup since {date}",statusOn:"{status} on {date}",windowFrom:"from {time}",windowUntil:"until {time}",noUndatedParcels:"Every active parcel has a delivery date.",noUndatedMatch:"No parcels without a date match this filter.",tabReview:"Needs review",tabFiltered:"Filtered",tabCount:"{label} ({count})",possibleDuplicate:"Possible duplicate",suggestionTitle:"Same parcel as {parcel}?",suggestionHint:"Merge the parcel that is the same one, or keep them apart.",reasonIs:"Reason: {reason}",mergeSuggested:"Merge",mergeSuggestedLabel:"Merge {candidate} into {title}",keepApart:"Keep apart",keepApartLabel:"Keep {title} apart from these parcels",reviewTabs:"Review lists",emptyReview:"Nothing to review.",emptyFiltered:"No filtered e-mails.",filteredHint:"E-mails the local AI classed as not about a parcel.",receivedOn:"Received {date}",noSubject:"(no subject)",mailboxOf:"Mailbox: {owner}",unverifiedSender:"Unverified sender",unverifiedSenderHint:"This e-mail didn't pass the sender checks (DKIM/DMARC). Make sure it's genuine before you accept it.",aiSuggestionLabel:"read by the local AI",suggestion:"Suggestion",noSuggestion:"No suggestion. Use Edit to enter the details yourself.",accept:"Accept",acceptWithChanges:"Accept with changes",edit:"Edit",dismiss:"Dismiss",trustSender:"Trust this sender",trustSenderHint:"Treat e-mails from {domain} as a known sender from now on",trustQuestion:"Trust {domain}? This e-mail failed the sender checks, and anyone can send e-mail that claims to come from {domain}. Its e-mails waiting here will be added as they are.",trustConfirm:"Trust {domain}",trustedSenderNote:"You trust {domain}, but this e-mail failed the sender checks. Make sure it's genuine before you accept it.",trustDone:"Trusted {domain}.",trustDoneWith:"Trusted {domain}: {parts}.",trustAddedOne:"added 1 e-mail",trustAddedMany:"added {count} e-mails",trustRecheckOne:"reading 1 e-mail again",trustRecheckMany:"reading {count} e-mails again",trustKeptOne:"1 still needs review",trustKeptMany:"{count} still need review",senderChecks:"Sender check details",checkHeaders:"Authentication headers",checkServers:"Servers, in order",checkNoServer:"(no name)",checkOriginals:"Renamed by the mail provider",checkUsed:"Header used",checkUsedNone:"None",checkUsedHeader:"Header {n}",checkNoResult:"none",ignoreSender:"Ignore this sender",ignoreSenderHint:"Skip e-mails from {domain} from now on",restore:"Restore",clear:"Clear",clearHint:"Remove this e-mail from the list. It won't be read again.",clearAll:"Clear all",clearAllQuestion:"Clear all filtered e-mails? They won't be read again.",aiQueueOne:"1 e-mail waiting for the local AI",aiQueueMany:"{count} e-mails waiting for the local AI",aiQueueMinutes:"{queue}, about {minutes} min",aiQueueHours:"{queue}, about {hours} h",fieldKind:"Type",fieldMerchant:"Merchant",fieldCarrier:"Carrier",fieldTrackingNumber:"Tracking number",fieldTrackingNumbers:"Tracking numbers",fieldOrderNumbers:"Order numbers",fieldEtaStart:"Expected from",fieldEtaEnd:"Expected until",fieldWindowStart:"Time window from",fieldWindowEnd:"Time window until",fieldPickupPoint:"Pickup point",fieldPickupCode:"PIN or pickup code",fieldItems:"Items",fieldPrivate:"Private (only the owners can see it)",hintList:"Separate with commas or new lines.",hintItems:"One per line.",carrierAuto:"Detect automatically",carrierUnknown:"Unknown",details:"Parcel details",status:"Status",sinceDate:"since {date}",carrier:"Delivered by",notKnownYet:"Not known yet",trackOnline:"Track on the carrier's site",opensInNewTab:"(opens in a new tab)",trackingNumber:"Tracking number",copy:"Copy",copyTrackingNumber:"Copy the tracking number",copied:"Copied.",copyFailed:"Couldn't copy automatically. The number is selected, so you can copy it yourself.",merchant:"Merchant",orders:"Orders",items:"Items",expected:"Expected",timeWindow:"Time window",pickupPoint:"Pickup point",pickupCode:"PIN or pickup code",packagesInShipment:"Packages",showPackage:"Show package {name}",parcelId:"Parcel ID",delivered:"Delivered",timeline:"Timeline",noTimeline:"No events yet.",provisional:"Provisional",provisionalHint:"Made from an order e-mail. It's completed when the shipping e-mail arrives.",archived:"Archived",private:"Private",loadingDetails:"Loading details\u2026",detailsError:"Couldn't load the details: {message}",retry:"Try again",notFound:"This parcel no longer exists.",aiNotice:"Found by the local AI. Check the details, then confirm them.",aiFilledNotice:"Some details were filled in by the local AI. Check them, then confirm.",confirm:"Confirm",confirmLabel:"Confirm the details the local AI found",confirmFilledLabel:"Confirm the details the local AI filled in",mergedNotice:"Merged automatically ({reason}). Check that it's one parcel.",mergedNoticeNoReason:"Merged automatically. Check that it's one parcel.",inferredNotice:"Probably delivered: another parcel from this shop was delivered around the expected day. Undo if it hasn't arrived.",markDelivered:"Mark delivered",editDate:"Edit date",checkAgain:"Check again",checkingAgain:"Checking\u2026",checkAgainHint:"Read this parcel's e-mails again, and let the local AI look for what's missing",checkAgainReadOne:"Read 1 e-mail again.",checkAgainReadMany:"Read {count} e-mails again.",checkAgainGoneOne:"1 e-mail is no longer in the mailbox.",checkAgainGoneMany:"{count} e-mails are no longer in the mailbox.",checkAgainFailedOne:"1 e-mail couldn't be downloaded; try again later.",checkAgainFailedMany:"{count} e-mails couldn't be downloaded; try again later.",checkAgainNoEmails:"This parcel has no e-mails to read again.",checkAgainQueuedOne:"The local AI is checking 1 e-mail.",checkAgainQueuedMany:"The local AI is checking {count} e-mails.",checkAgainSuggest:"What it finds waits under Needs review.",checkAgainAuto:"What it finds is added to this parcel.",checkAgainNothingForAi:"There was nothing for the local AI to fill in.",checkAgainAiOff:"The local AI is off.",mergeWith:"Merge with\u2026",split:"Split\u2026",archive:"Archive",actions:"Actions",mergeIntro:"Choose the parcel to merge into this one. Likely matches come first.",mergeChoose:"Parcel",mergeConfirm:"Merge",mergeChooseFirst:"Choose a parcel first.",mergeSearch:"Search",mergeSearchPlaceholder:"Shop, item, order, number or carrier",mergeShowOlder:"Show older ({count})",mergeNoMatch:"No parcel matches the search.",noMergeCandidates:"There are no other parcels to merge with.",numberTail:"No. {tail}",orderTail:"Order {tail}",splitIntro:"Choose what to move to a new parcel.",splitConfirm:"Split off",splitHint:"Choose at least one, but not all of them.",archiveQuestion:"Archive this parcel? It no longer counts as active.",dateEndBeforeStart:"The end date is before the start date.",dateEndWithoutStart:"Set a start date too.",windowEndBeforeStart:"The time window must end after it starts.",actionFailed:"That didn't work: {message}",addTitle:"Add parcel",addSubmit:"Add",trackingRequired:"Enter a tracking number."},Br={ordered:"Ordered",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",exception:"Problem with delivery",ready_for_pickup:"Ready for pickup",returned:"Returned",cancelled:"Cancelled"},Qe={order:"Order confirmation",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",ready_for_pickup:"Ready for pickup",delayed:"Delayed",customs:"Held at customs",return:"Return",cancelled:"Cancelled",code:"Delivery code",not_parcel:"Not about a parcel",unknown:"Unknown"},zr={parser:"E-mail",ai:"Local AI",manual:"Added by hand",seventeentrack:"17TRACK",inferred:"Inferred from another delivery"},jr={unknown_sender:"Unknown sender",not_aligned:"The sender's domain isn't authenticated (DKIM/DMARC)",no_auth_header:"No authentication results in the e-mail",untrusted_authserv:"Authentication results from an unknown server",multiple_auth_results:"More than one set of authentication results, so it can't tell which is real",low_confidence:"Not sure about the details",unknown_format:"Unknown e-mail format",ai_suggestion:"Read by the local AI",ai_fill:"The local AI found details the parser missed",ai_unavailable:"The local AI wasn't available",ai_timeout:"The local AI took too long on this e-mail",ai_rejected:"The local AI's answer didn't pass the checks",restored:"Moved back from Filtered"},Kr={same_number:"same tracking number",same_merchant_eta:"same shop and delivery date",same_merchant_day:"same shop, delivered on the expected day",same_merchant_domain:"the shop's tracked shipment followed its order",same_order:"same order"};function m(t,e){return t.replace(/\{(\w+)\}/g,(r,i)=>Object.hasOwn(e,i)?String(e[i]):r)}function I(t){if(typeof t=="string"&&t.trim())return t;if(t&&typeof t=="object"){let e=t.message;if(typeof e=="string"&&e.trim())return e;let r=t.code;if(typeof r=="string"&&r.trim())return r}return s.unknownError}var _n=["a[href]","button:not([disabled])","input:not([disabled]):not([type='hidden'])","select:not([disabled])","textarea:not([disabled])","[tabindex]:not([tabindex='-1'])"].join(",");function bn(t){return[...t.querySelectorAll(_n)].filter(e=>!e.closest("[hidden], [inert]")&&e.getClientRects().length>0)}function Wr(t,e){if(t.key!=="Tab"||t.altKey||t.ctrlKey||t.metaKey)return;let r=bn(e),i=r[0],n=r[r.length-1];if(!i||!n){t.preventDefault(),e.focus();return}let a=e.getRootNode().activeElement,d=a instanceof HTMLElement&&e.contains(a)&&a!==e;t.shiftKey&&(!d||a===i)?(t.preventDefault(),n.focus()):!t.shiftKey&&(!d||a===n)&&(t.preventDefault(),i.focus())}var vn="parcels-error",ge=class extends D{static properties={hass:{attribute:!1},_open:{state:!0},_busy:{state:!0},_error:{state:!0}};_returnFocus=null;_pressedBackdrop=!1;_hadFocus=!1;_session=0;constructor(){super(),this.hass=void 0,this._open=!1,this._busy=!1,this._error=null}render(){return l`<dialog
      aria-labelledby="dialog-title"
      @close=${this._onClose}
      @keydown=${this._onKeyDown}
      @pointerdown=${this._onPointerDown}
      @click=${this._onClick}
    >
      ${this._open?this.renderContent():u}
    </dialog>`}renderContent(){return u}canLightDismiss(){return!this._busy}dialogClosed(){}get isOpen(){return this._open}async showDialog(e){this._session+=1,this._returnFocus=e,this._open=!0,this._busy=!1,this._error=null,await this.updateComplete;let r=this._dialog();!r||!this._open||!this.isConnected||(r.open||r.showModal(),this.focusInDialog("[data-autofocus]"))}closeDialog(){let e=this._dialog();e?.open&&e.close(),this._finishClose(!0)}focusInDialog(e){this.renderRoot.querySelector(`dialog ${e}`)?.focus()}async focusAfterRender(e){await this.updateComplete,this._open&&this.focusInDialog(e)}async runAction(e,r){if(this._busy)return;let i=this._session;this._busy=!0,this._error=null;try{await e(),this._open&&this._session===i&&r?.()}catch(n){let o=m(s.actionFailed,{message:I(n)});this._open&&this._session===i?this._error=o:this.dispatchEvent(new CustomEvent(vn,{detail:o}))}finally{this._session===i&&(this._busy=!1)}}disconnectedCallback(){super.disconnectedCallback(),this._finishClose(!1)}willUpdate(e){this._hadFocus=this._open&&!!this.shadowRoot?.activeElement}updated(e){this._hadFocus&&this._open&&!this.shadowRoot?.activeElement&&this.focusInDialog("[data-autofocus]"),this._hadFocus=!1}_dialog(){return this.renderRoot.querySelector("dialog")}_finishClose(e){if(!this._open)return;let r=this._returnFocus;this._returnFocus=null,this._open=!1,this._busy=!1,this._error=null,this._pressedBackdrop=!1,this.dialogClosed(),e&&r?.()}_onClose(e){let r=e.currentTarget;e.target===r&&!r.open&&this._finishClose(!0)}_onKeyDown(e){Wr(e,e.currentTarget)}_onPointerDown(e){this._pressedBackdrop=e.target===e.currentTarget}_onClick(e){let r=this._pressedBackdrop&&e.target===e.currentTarget;this._pressedBackdrop=!1,r&&this.canLightDismiss()&&this.closeDialog()}};var yn=/^(\d{4})-(\d{2})-(\d{2})$/,$n=/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)(?:[.,](\d+))?(Z|[+-]\d{2}(?::?\d{2})?)?$/i,wn=[31,28,31,30,31,30,31,31,30,31,30,31];function xn(t){return t%4===0&&t%100!==0||t%400===0}function kn(t,e){return e===2&&xn(t)?29:wn[e-1]??0}function Xe(t){if(typeof t!="string")return null;let e=yn.exec(t);if(!e)return null;let r=Number(e[1]),i=Number(e[2]),n=Number(e[3]);return i<1||i>12||n<1||n>kn(r,i)?null:{year:r,month:i,day:n}}function Y(t){return Xe(t)!==null}function Ze(t){let e=Xe(t);if(!e)throw new RangeError(`Not a YYYY-MM-DD date: ${t}`);return e}function Je({year:t,month:e,day:r}){let i=e<=2?t-1:t,n=Math.floor(i/400),o=i-n*400,a=(e+9)%12,d=Math.floor((153*a+2)/5)+r-1,c=o*365+Math.floor(o/4)-Math.floor(o/100)+d;return n*146097+c-719468}function Sn(t){let e=t+719468,r=Math.floor(e/146097),i=e-r*146097,n=Math.floor((i-Math.floor(i/1460)+Math.floor(i/36524)-Math.floor(i/146096))/365),o=i-(365*n+Math.floor(n/4)-Math.floor(n/100)),a=Math.floor((5*o+2)/153),d=o-Math.floor((153*a+2)/5)+1,c=a<10?a+3:a-9;return{year:n+r*400+(c<=2?1:0),month:c,day:d}}function Tn({year:t,month:e,day:r}){return`${String(t).padStart(4,"0")}-${String(e).padStart(2,"0")}-${String(r).padStart(2,"0")}`}function ee(t,e){return Tn(Sn(Je(Ze(t))+e))}function ce(t,e){return Je(Ze(e))-Je(Ze(t))}function An(t){return((Je(Ze(t))+3)%7+7)%7}function et(t){return ee(t,-An(t))}function Yr(t){return Array.from({length:7},(e,r)=>ee(t,r))}function w(t,e){return t<e?-1:t>e?1:0}function Gr(t,e){return w(t,e)>=0?t:e}function N(t){if(typeof t!="string")return null;let e=$n.exec(t.trim());if(!e)return null;let[,r,i,n,o]=e;if(!r||!i||!Y(r))return null;let a=n?`.${n.slice(0,3).padEnd(3,"0")}`:"",d="Z";if(o&&o.toUpperCase()!=="Z"){let h=o.slice(1).replace(":","").padEnd(4,"0");d=`${o[0]}${h.slice(0,2)}:${h.slice(2,4)}`}let c=Date.parse(`${r}T${i}${a}${d}`);return Number.isNaN(c)?null:c}var qr=new Map;function Cn(t){let e=qr.get(t);if(!e){let r={calendar:"gregory",numberingSystem:"latn",year:"numeric",month:"2-digit",day:"2-digit"};try{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:t})}catch{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:"UTC"})}qr.set(t,e)}return e}function E(t,e){if(Y(t))return t;let r=N(t);if(r===null)return null;let i="",n="",o="";for(let d of Cn(e).formatToParts(r))d.type==="year"?i=d.value:d.type==="month"?n=d.value:d.type==="day"&&(o=d.value);let a=`${i.padStart(4,"0")}-${n}-${o}`;return Y(a)?a:null}function En(t){return[...new Set(t)]}function Vr(t){return En(t.split(/[\n,;]+/).map(e=>e.trim()).filter(Boolean))}function Pn(t){return t.split(/\r?\n/).map(e=>e.trim()).filter(Boolean)}function U(t){let e=/^(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?$/.exec((t??"").trim());if(!e)return null;let r=Number(e[1]),i=Number(e[2]);return r>23||i>59?null:`${String(r).padStart(2,"0")}:${String(i).padStart(2,"0")}`}function H(t){let e=t.trim();return e||null}function Rn(t,e){return e&&!t?s.dateEndWithoutStart:t&&e&&w(e,t)<0?s.dateEndBeforeStart:null}function Mn(t,e){let r=U(t),i=U(e);return r&&i&&i<=r?s.windowEndBeforeStart:null}function Qr(t){return{eta_start:t.eta_start??"",eta_end:t.eta_end??"",window_start:U(t.window_start)??"",window_end:U(t.window_end)??""}}function tt(t){let e=Rn(t.eta_start,t.eta_end);if(e)return{message:e,field:e===s.dateEndWithoutStart?"eta_start":"eta_end"};let r=Mn(t.window_start,t.window_end);return r?{message:r,field:"window_end"}:null}function Zr(t,e){return{parcel_id:t,eta_start:H(e.eta_start),eta_end:H(e.eta_end),window_start:U(e.window_start),window_end:U(e.window_end)}}var Jr="shipped";function It(t){return{kind:t?.kind||Jr,merchant:t?.merchant??"",carrier:t?.carrier??"",tracking_numbers:(t?.tracking_numbers??[]).join(", "),order_numbers:(t?.order_numbers??[]).join(", "),eta_start:t?.eta_start??"",eta_end:t?.eta_end??"",window_start:U(t?.window_start)??"",window_end:U(t?.window_end)??"",pickup_point:t?.pickup_point??"",pickup_code:t?.pickup_code??"",items:(t?.items??[]).join(`
`)}}function Xr(t){return{kind:t.kind.trim()||Jr,merchant:H(t.merchant),carrier:H(t.carrier),tracking_numbers:Vr(t.tracking_numbers),order_numbers:Vr(t.order_numbers),eta_start:H(t.eta_start),eta_end:H(t.eta_end),window_start:U(t.window_start),window_end:U(t.window_end),pickup_point:H(t.pickup_point),pickup_code:H(t.pickup_code),items:Pn(t.items)}}function ei(t){let e=t.tracking_number.trim();if(!e)return null;let r={tracking_number:e},i=H(t.carrier);i&&(r.carrier=i);let n=H(t.merchant);return n&&(r.merchant=n),t.private&&(r.private=!0),r}function Lt(t,e){return t.length>0&&t.length<e}var In="https://github.com/fratei/ha-parcels";function B(t,e){customElements.get(t)||customElements.define(t,e)}function _e(t,e,r){let i=window;Array.isArray(i.customCards)||(i.customCards=[]);let n=i.customCards;n.some(o=>o?.type===t)||n.push({type:t,name:e,description:r,preview:!0,documentationURL:In})}var z=x`
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
`,rt=x`
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
`,it=x`
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
`;var ti={tracking_number:"",carrier:"",merchant:"",private:!1},Dt=class extends ge{static properties={_form:{state:!0},_missingNumber:{state:!0}};static styles=[z,it,x`
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
    `];constructor(){super(),this._form=ti,this._missingNumber=!1}async open(e=null){this._form=ti,this._missingNumber=!1,await this.showDialog(e)}canLightDismiss(){return!1}renderContent(){let e=this._form,r=this._missingNumber;return l`
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
              .value=${C(e.tracking_number)}
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
              ${Ve().map(i=>l`<option value=${i.id} ?selected=${e.carrier===i.id}>
                    ${i.name}
                  </option>`)}
            </select>
          </label>
          <label class="field">
            <span class="field-label">${s.fieldMerchant}</span>
            <input
              name="merchant"
              autocomplete="off"
              .value=${C(e.merchant)}
              @input=${this._onInput}
            />
          </label>
          <label class="check-row">
            <input
              type="checkbox"
              name="private"
              .checked=${C(e.private)}
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
    `}_onInput(e){let r=e.currentTarget,i=r.name,n=r instanceof HTMLInputElement&&r.type==="checkbox"?r.checked:r.value;this._form={...this._form,[i]:n},i==="tracking_number"&&this._missingNumber&&r.value.trim()&&(this._missingNumber=!1)}_submit(e){e.preventDefault();let r=this.hass;if(!r||this._busy)return;let i=ei(this._form);if(!i){this._missingNumber=!0,this.focusAfterRender("#tracking-number");return}this.runAction(()=>Z(r,"add",i),()=>this.closeDialog())}};B("parcels-add-dialog",Dt);var Pe=V(class extends O{constructor(t){if(super(t),t.type!==A.ATTRIBUTE||t.name!=="class"||t.strings?.length>2)throw Error("`classMap()` can only be used in the `class` attribute and must be the only part in the attribute.")}render(t){return" "+Object.keys(t).filter(e=>t[e]).join(" ")+" "}update(t,[e]){if(this.st===void 0){this.st=new Set,t.strings!==void 0&&(this.nt=new Set(t.strings.join(" ").split(/\s/).filter(i=>i!=="")));for(let i in e)e[i]&&!this.nt?.has(i)&&this.st.add(i);return this.render(e)}let r=t.element.classList;for(let i of this.st)i in e||(r.remove(i),this.st.delete(i));for(let i in e){let n=!!e[i];n===this.st.has(i)||this.nt?.has(i)||(n?(r.add(i),this.st.add(i)):(r.remove(i),this.st.delete(i)))}return $}});function Ln(t){try{return Intl.DateTimeFormat.supportedLocalesOf([t]),t}catch{return"en"}}function Dn(){let t=new Intl.DateTimeFormat(void 0,{hour:"numeric"}).resolvedOptions().hourCycle;return t==="h11"||t==="h12"}function st(t,e){let r=Ln(t?.locale?.language||t?.language||"en"),i=t?.locale?.time_format,n;i==="12"?n=!0:i==="24"?n=!1:i==="system"&&(n=Dn());let o=t?.locale?.time_zone==="local"?void 0:e||t?.config?.time_zone||void 0;return{language:r,hour12:n,timeZone:o}}var ri=new Map;function Re(t,e,r){let i=e.hour!==void 0||e.timeStyle!==void 0,n={...e,timeZone:r?"UTC":t.timeZone};i&&t.hour12!==void 0&&(n.hour12=t.hour12);let o=JSON.stringify([t.language,n]),a=ri.get(o);if(!a){try{a=new Intl.DateTimeFormat(t.language,n)}catch{a=new Intl.DateTimeFormat(t.language,{...n,timeZone:void 0})}ri.set(o,a)}return a}function Ot(t){let e=Xe(t);return e?new Date(Date.UTC(e.year,e.month-1,e.day)):null}var ii={weekday:"short",day:"numeric",month:"short"},ni={day:"numeric",month:"short",year:"numeric"};function ue(t,e,r=ii){let i=Ot(t);return i?Re(e,r,!0).format(i):t}function R(t,e,r,i=ii){let n=Ot(t),o=Ot(e);return!n||!o?[t,e].filter(Boolean).join(" \u2013 "):t===e?Re(r,i,!0).format(n):Re(r,i,!0).formatRange(n,o)}function nt(t,e){let r=/^(\d{1,2}):(\d{2})/.exec(t);if(!r)return t;let i=new Date(Date.UTC(1970,0,1,Number(r[1]),Number(r[2])));return Re(e,{hour:"numeric",minute:"2-digit"},!0).format(i)}function be(t,e,r){return t&&e?`${nt(t,r)}\u2013${nt(e,r)}`:t?m(s.windowFrom,{time:nt(t,r)}):e?m(s.windowUntil,{time:nt(e,r)}):null}function j(t,e){if(!t)return"";let r=N(t);return r===null?t:Re(e,{dateStyle:"medium",timeStyle:"short"},!1).format(r)}function Me(t){if(typeof t!="string")return null;let e=t.trim();return e||null}function si(t){let e=t.trim();if(!/^[a-z0-9]+(?:[_-][a-z0-9]+)*$/.test(e))return e;let r=e.replace(/[_-]+/g," ");return r.charAt(0).toUpperCase()+r.slice(1)}function Ie(t,e){let r=Me(e);return r?Object.hasOwn(t,r)?t[r]??r:si(r):""}function M(t){let e=Me(t.carrier_name);if(e)return e;let r=Me(t.carrier);return!r||r==="other"?null:Object.hasOwn(X,r)?Ur(r):si(r)}function L(t){return t.restricted?s.privateParcel:Me(t.merchant)??M(t)??Me(t.tracking_number)??s.unnamedParcel}function G(t){return Ie(Br,t)}function Ft(t){return Ie(Qe,t)}function Nt(t){return Ie(zr,t)}function oi(t){return Ie(jr,t)}function ot(t){return Ie(Kr,t)}var at="var(--secondary-text-color, #727272)",ai="var(--info-color, #039be5)",On="var(--warning-color, #ffa600)",Fn="var(--success-color, #43a047)",li="var(--error-color, #db4437)",Nn="var(--purple-color, #926bc7)",di={ordered:at,shipped:ai,in_transit:ai,out_for_delivery:On,delivered:Fn,attempted:li,exception:li,ready_for_pickup:Nn,returned:at,cancelled:at};function Le(t){return Object.hasOwn(di,t)?di[t]:at}var Hn=new Set(["delivered","returned","cancelled"]);function pe(t){return!Hn.has(t)}function k(t){let e=Y(t.eta_start)?t.eta_start:null,r=Y(t.eta_end)?t.eta_end:null,i=e??r;return i?{start:i,end:r&&w(r,i)>=0?r:i}:null}function te(t){return pe(t.status)}function Ht(t,e){let r=N(t.status_time),i=N(e.status_time);return r!==i?r===null?1:i===null?-1:i-r:t.id<e.id?-1:t.id>e.id?1:0}function mi(t){return t.filter(e=>te(e)&&!e.archived&&k(e)===null).sort(Ht)}var Un=7,Bn=9999;function ci(t){return t.replace(/[^0-9a-z]/gi,"").toUpperCase()}function ui(t){return t.merchant?.trim().toLowerCase()??""}function pi(t,e){let r=k(t);if(r)return r;let i=E(t.delivered_at??t.status_time,e);return i?{start:i,end:i}:null}function hi(t,e,r){let i=pi(t,r),n=pi(e,r);return!i||!n?Bn:w(i.end,n.start)<0?ce(i.end,n.start):w(n.end,i.start)<0?ce(n.end,i.start):0}function Ut(t,{timeZone:e}){let r=new Set(t.order_numbers.map(ci).filter(Boolean)),i=ui(t),n=o=>o.order_numbers.some(a=>r.has(ci(a)))?0:i&&ui(o)===i?1:2;return(o,a)=>n(o)-n(a)||+!te(o)-+!te(a)||hi(t,o,e)-hi(t,a,e)||Ht(o,a)}function zn(t,{today:e,timeZone:r}){if(t.archived||t.status==="cancelled")return!0;if(te(t))return!1;let i=E(t.delivered_at??t.status_time,r);return i!==null&&ce(i,e)>Un}function fi(t,e,r){let i=[],n=[];for(let o of t)o.id===e.id||o.restricted||(zn(o,r)?n:i).push(o);return i.sort(Ut(e,r)),n.sort(Ht),{likely:i,older:n}}function gi(t,e){let r=e.toLowerCase().split(/\s+/).filter(Boolean);return r.length?t.filter(i=>{let n=[i.merchant,M(i),i.tracking_number,...i.order_numbers,...i.items].filter(Boolean).join(" ").toLowerCase();return r.every(o=>n.includes(o))}):[...t]}function _i(t){let e=new Map;for(let r of t??[]){let i=e.get(r.parcel.id)??[];for(let n of r.candidates)i.some(o=>o.id===n.id)||i.push(n);e.set(r.parcel.id,i)}return e}function bi(t,e){let r=[],i=new Set,n=(o,a,d)=>{i.has(a.id)||(i.add(a.id),r.push({suggestionId:o,parcel:a,candidateId:d}))};for(let o of t??[])if(o.parcel.id===e)for(let a of o.candidates)n(o.id,a,a.id);else o.candidates.some(a=>a.id===e)&&n(o.id,o.parcel,e);return r}function $i(t,e,r){return e?.kind==="delivered"||e?.kind==="returned"?null:be(t.window_start,t.window_end,r)}function wi(t){return!t.restricted&&M(t)===null}function xi(t){return t!==void 0&&t>1?m(s.packages,{count:String(t)}):null}function lt(t){return t.restricted?s.privateParcel:dt(t.merchant)??s.unknownSeller}function Bt(t){if(t.restricted)return null;let e=dt(t.pickup_code);return e?m(s.pin,{code:e}):null}function ki(t,e){let r=e.placement??null,i=[],n=M(t);if(n&&i.push(n),e.showStatus){let d=G(t.status);d&&i.push(d)}let o=xi(e.count);o&&i.push(o),e.showRange&&r&&r.from!==r.to&&i.push(R(r.from,r.to,e.locale));let a=$i(t,r,e.locale);return a&&i.push(a),wi(t)&&i.push(s.carrierNotKnown),i.join(" \xB7 ")}var jn=/^\d{1,3}\s*[x×]\s+/i,Kn=/\s*(?:[,;(|[]|\s[-–—]\s)/,vi=8;function dt(t){if(typeof t!="string")return null;let e=t.replace(/\s+/g," ").trim();return e||null}function Si(t){let e=t.replace(jn,""),r=e.search(Kn);return(r>0?e.slice(0,r):e).trim()||t}function Ti(t){let e=Si(t).split(" ").slice(0,3);for(;e.length>1&&e.join(" ").length>24;)e.pop();return e.join(" ")}function Wn(t){let e=Si(t).split(" "),r=e[0]??t;return r.length<4&&e.length>1?`${r} ${e[1]}`:r}function De(t){if(t.restricted)return null;let e=(t.items??[]).map(dt).filter(n=>n!==null);if(e.length===0)return null;if(e.length===1)return e[0]??null;let r=e.map(e.length===2?Ti:Wn),i=r.slice(0,vi);return r.length>vi&&i.push("\u2026"),`${m(s.itemsCount,{count:String(e.length)})} \xB7 ${i.join(", ")}`}function qn(t){let e=(t.items??[]).map(dt).filter(n=>n!==null),r=e[0];if(t.restricted||r===void 0)return null;let i=Ti(r);return e.length>1?m(s.itemsMore,{name:i,count:String(e.length-1)}):i}function Ai(t){let e=t.length===1?t[0]:void 0;if(e!==void 0){let i=De(e);return i?m(s.possibly,{items:i}):null}let r=[...new Set(t.map(qn).filter(i=>i!==null))];return r.length?m(s.possibly,{items:r.join(s.possiblyOr)}):null}function Ci(t,e){let{locale:r}=e,i=e.placement??null,n=[lt(t)],o=xi(e.count);o&&n.push(o);let a=M(t);a?n.push(m(s.carrierIs,{carrier:a})):wi(t)&&n.push(s.carrierNotKnownLabel);let d=G(t.status),c=i?ue(i.from,r):"";switch(i?.kind){case"delivered":n.push(m(s.deliveredOn,{date:c}));break;case"returned":n.push(m(s.returnedOn,{date:c}));break;case"pickup":n.push(m(s.readyForPickupSince,{date:c}));break;case"status":n.push(m(s.statusOn,{status:d,date:c}));break;case"eta":d&&n.push(d),n.push(m(s.expectedOn,{date:R(i.from,i.to,r)}));break;default:d&&n.push(d);break}let h=$i(t,i,r);h&&n.push(h);let f=De(t);if(f?n.push(f):e.possibly&&!t.restricted&&n.push(e.possibly),!t.restricted){t.ai?n.push(s.aiBadgeLabel):t.ai_filled&&n.push(s.aiFilledLabel),t.auto_merged&&n.push(s.autoMergedLabel),t.inferred&&n.push(s.inferredLabel);let p=Bt(t);p?n.push(p):t.has_code&&n.push(s.hasCode)}return(t.private||t.restricted)&&n.push(s.privateLabel),e.continuesBefore&&n.push(s.continuesBefore),e.continuesAfter&&n.push(s.continuesAfter),n.join(", ")}function yi(t){let e=t?.trim();return e?e.length<=6?e:`\u2026${e.replace(/[^0-9a-z]/gi,"").slice(-5)}`:null}function he(t,e){let r=null;if(te(t)){let a=k(t);r=a?R(a.start,a.end,e):null}else{let a=e.timeZone??Intl.DateTimeFormat().resolvedOptions().timeZone,d=E(t.delivered_at??t.status_time,a);r=d?R(d,d,e):null}let i=[M(t)??s.carrierNotKnown],n=yi(t.tracking_number);n&&i.push(m(s.numberTail,{tail:n}));let o=yi(t.order_numbers[0]);return o&&i.push(m(s.orderTail,{tail:o})),{title:lt(t),when:[G(t.status),r].filter(Boolean).join(" \xB7 "),carrier:i.join(" \xB7 "),items:De(t)}}function Oe(t,e){let r=he(t,e);return[r.title,r.items,r.carrier,r.when].filter(Boolean).join(" \xB7 ")}function zt(t,e){let r=[],i=new Map;for(let n of t){let o=e(n),a=o===null?void 0:i.get(o);if(a){a.push(n);continue}let d=[n];r.push(d),o!==null&&i.set(o,d)}return r}function jt(t,...e){return t.restricted||t.shipment_group===null?null:JSON.stringify([t.shipment_group,t.status,...e])}function ve(t,e){return t.id<e.id?-1:t.id>e.id?1:0}function Ei(t){return zt(t,e=>jt(e)).map(e=>{let r=[...e].sort(ve);return{parcel:e.reduce((i,n)=>ve(n,i)<0?n:i),members:r}})}function Yn(t){return t.reduce((e,r)=>r!==null&&(e===null||r<e)?r:e,null)}function Gn(t){return t.reduce((e,r)=>r!==null&&(e===null||r>e)?r:e,null)}function Pi(t,e){return e.length<2?t:{...t,window_start:Yn(e.map(r=>r.window_start)),window_end:Gn(e.map(r=>r.window_end)),ai:e.some(r=>r.ai),ai_filled:e.some(r=>r.ai_filled),private:e.some(r=>r.private),has_code:e.some(r=>r.has_code),pickup_code:Vn(e),items:Qn(t,e),auto_merged:e.find(r=>r.auto_merged)?.auto_merged??null,inferred:e.some(r=>r.inferred)}}function Vn(t){let e=new Set;for(let r of t){let i=r.pickup_code?.trim();i&&e.add(i)}return e.size>0?[...e].join(", "):null}function Qn(t,e){let r=[...t.items],i=new Set(r);for(let n of e)for(let o of n.items)i.has(o)||(i.add(o),r.push(o));return r}function Ri(t,e){let r=e.shipment_group;if(r===null||e.restricted)return[];let i=t.filter(n=>n.shipment_group===r&&!n.restricted).sort((n,o)=>(n.tracking_number??"").localeCompare(o.tracking_number??"","en",{numeric:!0})||ve(n,o));return i.length>1?i:[]}function Kt(t){return`.chip[data-parcels~="${CSS.escape(t)}"] button.chip-main`}function Ii(t,e,r,i){let n=e?"true":"false";return l`<div class="merge-note">
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
  </div>`}function Zn(t,e,r){let i=r&&(t.tracking_number?.trim()??null)||null;return{title:i?`${e} ${i}`:e,detail:i}}function Jn(t,e,r){let{title:i,detail:n}=e;return Ii({icon:"mdi:call-merge",label:s.autoMerged,detail:n,undoLabel:m(s.undoMergeLabel,{title:i}),keepLabel:m(s.keepMergeLabel,{title:i})},r.busy,()=>r.onUndoMerge(t),()=>r.onKeepMerge(t))}function Xn(t,e,r){let{title:i,detail:n}=e;return Ii({icon:"mdi:package-variant-closed-check",label:s.inferred,detail:n,undoLabel:m(s.undoInferredLabel,{title:i}),keepLabel:m(s.keepInferredLabel,{title:i})},r.busy,()=>r.onUndoInferred(t),()=>r.onKeepInferred(t))}var Mi="\xA0";function ct(t,e){let{locale:r}=e,i=e.placement??null,n=e.members&&e.members.length>1?e.members:[t],o=n.length>1,a=Pi(t,n),d=L(a),c=Bt(a),h=De(a),f=h===null&&!a.restricted?e.possibly??null:null,p=Ci(a,{locale:r,placement:i,count:n.length,continuesBefore:e.continuesBefore,continuesAfter:e.continuesAfter,possibly:f}),g=ki(a,{locale:r,placement:i,count:n.length,showStatus:e.showStatus,showRange:e.showRange}),_={chip:!0,"cont-before":e.continuesBefore===!0,"cont-after":e.continuesAfter===!0,returned:a.status==="returned"},b={...e.position,"--chip-color":Le(a.status)},S=l`<span class="chip-row" aria-hidden=${a.restricted?"true":u}>
    ${e.continuesBefore?l`<span class="cont">‹</span>`:u}
    ${a.status==="delivered"?l`<span class="check">✓</span>`:u}
    <span class="chip-text">
      <span class=${Pe({"chip-title":!0,unknown:!a.restricted&&!a.merchant?.trim()})}
        >${lt(a)}</span
      >
      <span class="chip-line">
        <span class="chip-meta">${g||Mi}</span>
        ${c?l`<span class="chip-pin">${c}</span>`:u}
      </span>
      <span
        class=${Pe({"chip-items":!0,unknown:h===null&&f===null&&!a.restricted,possibly:f!==null})}
        >${h??f??(a.restricted?Mi:s.itemsNotKnown)}</span
      >
    </span>
    ${(a.ai||a.ai_filled)&&!a.restricted?l`<span class="badge ai">${s.aiBadge}</span>`:u}
    ${a.has_code&&!c&&!a.restricted?l`<ha-icon class="lock" icon="mdi:dialpad" title=${s.hasCode}></ha-icon>`:u}
    ${a.private||a.restricted?l`<ha-icon class="lock" icon="mdi:lock"></ha-icon>`:u}
    ${e.continuesAfter?l`<span class="cont">›</span>`:u}
  </span>`;return a.restricted?l`<div class=${Pe(_)} style=${F(b)}>
      <div class="chip-main" title=${p}>
        <span class="sr-only">${p}</span>
        ${S}
      </div>
    </div>`:l`<div
    class=${Pe(_)}
    style=${F(b)}
    data-parcel-id=${a.id}
    data-parcels=${n.map(T=>T.id).join(" ")}
  >
    <button
      type="button"
      class="chip-main"
      aria-haspopup="dialog"
      aria-label=${p}
      title=${p}
      @click=${T=>e.onOpen(t,T.currentTarget)}
    >
      ${S}
    </button>
    ${n.map(T=>{let xe=Zn(T,d,o);return l`${T.auto_merged?Jn(T,xe,e):u}${T.inferred?Xn(T,xe,e):u}`})}
  </div>`}function Li(t,e){return e&&!t.restricted&&!t.archived&&te(t)&&k(t)===null}function ut(t){return typeof t=="number"&&Number.isInteger(t)&&t>0?t:0}function Wt(t){let e=t!==null&&typeof t=="object"?t:{};return{read:ut(e.read),queued:ut(e.queued),gone:ut(e.gone),failed:ut(e.failed)}}function pt(t,e,r){return t<=0?null:t===1?e:m(r,{count:t})}function Di(t,e){if(t.read+t.gone+t.failed===0)return s.checkAgainNoEmails;let r=[pt(t.read,s.checkAgainReadOne,s.checkAgainReadMany),pt(t.gone,s.checkAgainGoneOne,s.checkAgainGoneMany),pt(t.failed,s.checkAgainFailedOne,s.checkAgainFailedMany)];return t.queued>0?r.push(pt(t.queued,s.checkAgainQueuedOne,s.checkAgainQueuedMany),e.mode==="suggest"?s.checkAgainSuggest:s.checkAgainAuto):t.read>0&&r.push(e.enabled?s.checkAgainNothingForAi:s.checkAgainAiOff),r.filter(i=>i!==null).join(" ")}function P(t){return typeof t=="object"&&t!==null&&!Array.isArray(t)}function v(t){return typeof t=="string"?t:null}function y(t){return typeof t=="string"?t:""}function re(t){return Array.isArray(t)?t.filter(e=>typeof e=="string"):[]}function ne(t){return typeof t=="string"&&t!==""?t:null}function qt(t){return Number.isSafeInteger(t)&&t>0?t:0}function es(t){return typeof t=="number"&&Number.isFinite(t)&&t>=0?t:null}function ie(t,e){if(!Array.isArray(t))return[];let r=[];for(let i of t){let n=e(i);n!==null&&r.push(n)}return r}function Yt(t){return t==="ai"||t==="manual"||t==="seventeentrack"?t:"parser"}function ts(t){return!P(t)||!ne(t.origin)?null:{origin:y(t.origin),at:y(t.at),reason:y(t.reason)}}function ht(t){if(!P(t))return null;let e=ne(t.id);return e?{id:e,merchant:v(t.merchant),carrier:v(t.carrier),carrier_name:v(t.carrier_name),tracking_number:v(t.tracking_number),tracking_url:v(t.tracking_url),status:y(t.status),status_time:v(t.status_time),eta_start:v(t.eta_start),eta_end:v(t.eta_end),window_start:v(t.window_start),window_end:v(t.window_end),delivered_at:v(t.delivered_at),inferred:t.inferred===!0,pickup_point:v(t.pickup_point),pickup_code:v(t.pickup_code),has_code:t.has_code===!0,order_numbers:re(t.order_numbers),items:re(t.items),private:t.private===!0,owners:re(t.owners),source:Yt(t.source),ai:t.ai===!0,ai_filled:t.ai_filled===!0,auto_merged:ts(t.auto_merged),provisional:t.provisional===!0,archived:t.archived===!0,origins:re(t.origins),shipment_group:ne(t.shipment_group),restricted:t.restricted===!0}:null}function rs(t){return P(t)?{kind:y(t.kind),merchant:v(t.merchant),carrier:v(t.carrier),tracking_numbers:re(t.tracking_numbers),order_numbers:re(t.order_numbers),eta_start:v(t.eta_start),eta_end:v(t.eta_end),window_start:v(t.window_start),window_end:v(t.window_end),pickup_point:v(t.pickup_point),pickup_code:v(t.pickup_code),items:re(t.items)}:null}function is(t){if(!P(t))return null;let e=ne(t.id);return e?{id:e,created:y(t.created),received:v(t.received),sender:y(t.sender),sender_domain:y(t.sender_domain),subject:y(t.subject),mailbox_owner:v(t.mailbox_owner),reason:y(t.reason),authenticated:t.authenticated===!0,trusted_sender:t.trusted_sender===!0,checks:ns(t.checks),fill:t.fill===!0,source:t.source==="ai"?"ai":"parser",suggestion:rs(t.suggestion)}:null}function ns(t){if(!P(t))return null;let e=qt(t.headers),r=t.used;return{headers:e,servers:Array.isArray(t.servers)?t.servers.map(i=>typeof i=="string"?i:""):[],used:Number.isSafeInteger(r)&&r>=0&&r<e?r:null,dkim:y(t.dkim),dmarc:y(t.dmarc),spf:y(t.spf),originals:qt(t.originals)}}function ss(t){if(!P(t))return null;let e=ne(t.id);return e?{id:e,created:y(t.created),received:v(t.received),sender:y(t.sender),sender_domain:y(t.sender_domain),subject:y(t.subject)}:null}function os(t){if(!P(t))return null;let e=ne(t.id),r=ht(t.parcel),i=ie(t.candidates,ht);return!e||!r||!i.length?null:{id:e,reason:y(t.reason),merchant:v(t.merchant),day:Y(t.day)?t.day:null,parcel:r,candidates:i}}function as(t){return t==="suggest"||t==="auto"?t:"off"}function ls(t,e=Date.now()){let r=P(t)?t:{},i=ne(r.time_zone)??"UTC",n=Y(r.today)?r.today:E(new Date(e).toISOString(),i)??"1970-01-01";return{user_is_admin:r.user_is_admin===!0,ai_enabled:r.ai_enabled===!0,ai_mode:as(r.ai_mode),ai_queue:qt(r.ai_queue),ai_queue_seconds:es(r.ai_queue_seconds),dashboard_url:y(r.dashboard_url),seventeentrack:r.seventeentrack===!0,time_zone:i,today:n}}function Oi(t,e=Date.now()){let r=P(t)?t:{};return{parcels:ie(r.parcels,ht),review:ie(r.review,is),merge_suggestions:ie(r.merge_suggestions,os),filtered:ie(r.filtered,ss),settings:ls(r.settings,e)}}function ds(t){return P(t)?{time:y(t.time),status:y(t.status),source:t.source==="inferred"?"inferred":Yt(t.source),label:y(t.label)}:null}function cs(t){return P(t)?{id:y(t.id),merchant:v(t.merchant),number:y(t.number),placed_at:v(t.placed_at),parcel_ids:re(t.parcel_ids)}:null}function us(t){if(!P(t))return null;let e=ne(t.id);return e?{id:e,label:y(t.label),source:Yt(t.source),time:v(t.time)}:null}function Fi(t){if(!P(t))return null;let e=ht(t.parcel);return e?{parcel:e,timeline:ie(t.timeline,ds),orders:ie(t.orders,cs),origins:ie(t.origins,us)}:null}function Ni(t){if(typeof t!="string")return null;let e=t.trim();if(!e)return null;let r;try{r=new URL(e)}catch{return null}return r.protocol!=="https:"||!r.hostname||r.username||r.password?null:r.href}var ps={weekday:"short",day:"numeric",month:"short",year:"numeric"},Hi={eta_start:"",eta_end:"",window_start:"",window_end:""},hs=6;function ms(t){return t.map((e,r)=>({entry:e,index:r,time:N(e.time)??-1/0})).sort((e,r)=>r.time-e.time||r.index-e.index).map(({entry:e})=>e)}var Gt=class extends ge{static properties={snapshot:{attribute:!1},locale:{attribute:!1},_parcelId:{state:!0},_details:{state:!0},_loading:{state:!0},_loadError:{state:!0},_mode:{state:!0},_copyState:{state:!0},_dateForm:{state:!0},_formError:{state:!0},_mergeTarget:{state:!0},_mergeQuery:{state:!0},_mergeOlder:{state:!0},_mergeHint:{state:!0},_splitSelection:{state:!0},_pendingPrivate:{state:!0},_checking:{state:!0},_checkStatus:{state:!0}};static styles=[z,it,x`
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
    `];_request=0;_checkRun=0;_loadedKey="";constructor(){super(),this.snapshot=null,this.locale=st(void 0),this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._copyState="idle",this._dateForm=Hi,this._formError=null,this._mergeTarget="",this._mergeQuery="",this._mergeOlder=!1,this._mergeHint=!1,this._splitSelection=[],this._pendingPrivate=null,this._checking=!1,this._checkStatus=null}async open(e,r=null){this._parcelId=e,this._details=null,this._loadError=null,this._mode="view",this._copyState="idle",this._formError=null,this._pendingPrivate=null,this._checkRun+=1,this._checking=!1,this._checkStatus=null,this._load(),await this.showDialog(r)}_switchTo(e){this._busy||e===this._parcelId||(this._parcelId=e,this._details=null,this._loadError=null,this._error=null,this._mode="view",this._copyState="idle",this._formError=null,this._pendingPrivate=null,this._checkStatus=null,this._load(),this.focusAfterRender("[data-current-package]"))}dialogClosed(){this._request+=1,this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._pendingPrivate=null,this._checkRun+=1,this._checking=!1,this._checkStatus=null}canLightDismiss(){return this._mode==="view"&&!this._busy}willUpdate(e){if(super.willUpdate(e),!e.has("snapshot")||!this.isOpen||!this.snapshot)return;this._pendingPrivate=null;let r=this.snapshot.parcels.find(i=>i.id===this._parcelId);r&&JSON.stringify(r)!==this._loadedKey&&this._load()}get _parcel(){let e=this._parcelId;return e===null?null:this.snapshot?this.snapshot.parcels.find(r=>r.id===e)??null:this._details?.parcel??null}async _load(){let e=this.hass,r=this._parcelId;if(!e||r===null)return;let i=++this._request,n=this.snapshot?.parcels.find(o=>o.id===r);this._loadedKey=n?JSON.stringify(n):"",this._loading=!0,this._loadError=null;try{let o=await J(e,"get",{parcel_id:r});if(i!==this._request)return;let a=Fi(o);if(!a)throw new Error(s.unknownError);this._details=a}catch(o){i===this._request&&(this._loadError=I(o))}finally{i===this._request&&(this._loading=!1)}}renderContent(){let e=this._parcel;return l`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">
            ${e?L(e):s.details}
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
      ${e&&this._mode==="view"?this._renderCheckStatus():u}
      ${e&&!e.restricted?this._renderActions(e):u}
    `}_renderCheckStatus(){return l`<div class="dialog-status" role="status">
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
      <span class="badge" style=${F({"--badge-color":Le(e.status)})}>
        ${G(e.status)}
      </span>
      ${(e.ai||e.ai_filled)&&!e.restricted?l`<span class="badge ai" title=${r}>
            ${s.aiBadge}<span class="sr-only">, ${r}</span>
          </span>`:u}
      ${e.private||e.restricted?l`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${s.private}
          </span>`:u}
      ${e.provisional?l`<span class="badge info">${s.provisional}</span>`:u}
      ${e.archived?l`<span class="badge">${s.archived}</span>`:u}
    </div>`}_renderBody(e){if(!e)return this.snapshot||!this._loading&&!this._loadError?l`<p class="empty">${s.notFound}</p>`:this._renderLoadState();switch(this._mode){case"date":return this._renderDateForm();case"merge":return this._renderMerge(e);case"split":return this._renderSplit();case"archive":return l`<p>${s.archiveQuestion}</p>`;default:return this._renderView(e)}}_renderLoadState(){return this._loadError?l`<div class="alert error" role="alert">
        <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
        <span class="grow">${m(s.detailsError,{message:this._loadError})}</span>
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
              .checked=${C(this._pendingPrivate??e.private)}
              aria-disabled=${this._busy?"true":"false"}
              @click=${this._onPrivateClick}
              @change=${this._togglePrivate}
            />
            <span>${s.fieldPrivate}</span>
          </label>`}
      <h3 class="section-title">${s.timeline}</h3>
      ${this._details?this._renderTimeline(this._details.timeline):this._renderLoadState()}
    `}_renderPossible(e){let r=bi(this.snapshot?.merge_suggestions,e.id);if(!r.length)return u;let i=this.locale,n=this._busy?"true":"false",o=L(e);return l`<section class="possible" aria-labelledby="possible-title">
      <h3 class="section-title" id="possible-title">${s.possibleMatches}</h3>
      <p class="hint">${s.possibleMatchesHint}</p>
      <ul class="possible-list">
        ${r.map(a=>{let d=he(a.parcel,i),c=Oe(a.parcel,i);return l`<li class="possible-item" data-possible=${a.parcel.id}>
            <span class="merge-lines">
              <span class="merge-line"><strong>${d.title}</strong> · ${d.when}</span>
              <span class="merge-line muted">${d.carrier}</span>
              <span class="merge-line items ${d.items?"":"muted"}">
                ${d.items??s.itemsNotKnown}
              </span>
            </span>
            <span class="possible-actions">
              <button
                type="button"
                class="btn"
                data-accept
                aria-label=${m(s.mergeSuggestedLabel,{candidate:c,title:o})}
                aria-disabled=${n}
                @click=${()=>this._acceptPossible(a)}
              >
                ${s.mergeSuggested}
              </button>
              <button
                type="button"
                class="btn"
                data-dismiss
                aria-label=${m(s.notThisOneLabel,{candidate:c,title:o})}
                aria-disabled=${n}
                @click=${()=>this._dismissPossible(a)}
              >
                ${s.notThisOne}
              </button>
            </span>
          </li>`})}
      </ul>
    </section>`}_renderMergeNotice(e){let r=ot(e.auto_merged?.reason),i=this._busy?"true":"false",n=L(e);return l`<div class="alert warning">
      <ha-icon icon="mdi:call-merge" aria-hidden="true"></ha-icon>
      <span class="grow">
        ${r?m(s.mergedNotice,{reason:r}):s.mergedNoticeNoReason}
      </span>
      <button
        type="button"
        class="btn"
        aria-label=${m(s.undoMergeLabel,{title:n})}
        aria-disabled=${i}
        @click=${this._undoMerge}
      >
        ${s.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${m(s.keepMergeLabel,{title:n})}
        aria-disabled=${i}
        @click=${this._keepMerge}
      >
        ${s.keep}
      </button>
    </div>`}_renderInferredNotice(e){let r=this._busy?"true":"false",i=L(e);return l`<div class="alert warning">
      <ha-icon icon="mdi:package-variant-closed-check" aria-hidden="true"></ha-icon>
      <span class="grow">${s.inferredNotice}</span>
      <button
        type="button"
        class="btn"
        aria-label=${m(s.undoInferredLabel,{title:i})}
        aria-disabled=${r}
        @click=${this._undoInferred}
      >
        ${s.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${m(s.keepInferredLabel,{title:i})}
        aria-disabled=${r}
        @click=${this._keepInferred}
      >
        ${s.keep}
      </button>
    </div>`}_renderFacts(e){let r=this.locale,i=k(e),n=be(e.window_start,e.window_end,r),o=M(e),a=e.restricted?null:Ni(e.tracking_url),d=e.tracking_number?.trim()??"",c=this._details?.orders??[],h=Ri(this.snapshot?.parcels??[],e),f=this._details?.parcel.id===e.id?this._details.parcel:null,p=e.has_code?f?.pickup_code??null:null,g=(b,S)=>l`<div><dt>${b}</dt><dd>${S}</dd></div>`,_=e.status_time?` \xB7 ${m(s.sinceDate,{date:j(e.status_time,r)})}`:"";return l`<dl class="facts">
      ${g(s.status,`${G(e.status)}${_}`)}
      ${e.delivered_at?g(s.delivered,j(e.delivered_at,r)):u}
      ${i?g(s.expected,R(i.start,i.end,r,ps)):u}
      ${n?g(s.timeWindow,n):u}
      ${o||a||!e.restricted?g(s.carrier,l`${o??(e.restricted?"":s.notKnownYet)}${a?l`<a class="link" href=${a} target="_blank" rel="noopener noreferrer">
                  ${s.trackOnline}<span class="sr-only"> ${s.opensInNewTab}</span>
                  <ha-icon icon="mdi:open-in-new" aria-hidden="true"></ha-icon>
                </a>`:u}`):u}
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
          </div>`:u}
      ${h.length?g(s.packagesInShipment,l`<ul class="packages">
              ${h.map(b=>this._renderPackage(b,e.id))}
            </ul>`):u}
      ${e.merchant?g(s.merchant,e.merchant):u}
      ${c.length?g(s.orders,l`<ul>
              ${c.map(b=>l`<li>
                    ${b.number}${b.placed_at?` \xB7 ${j(b.placed_at,r)}`:""}
                  </li>`)}
            </ul>`):e.order_numbers.length?g(s.orders,e.order_numbers.join(", ")):u}
      ${e.items.length?g(s.items,l`<ul>
              ${e.items.map(b=>l`<li>${b}</li>`)}
            </ul>`):u}
      ${e.pickup_point?g(s.pickupPoint,e.pickup_point):u}
      ${p?g(s.pickupCode,p):u}
      ${e.restricted?u:g(s.parcelId,e.id)}
    </dl>`}_renderPackage(e,r){let i=this.locale,n=e.tracking_number?.trim()||L(e),o=k(e),a=e.delivered_at?j(e.delivered_at,i):o?R(o.start,o.end,i):"",d=[G(e.status),a].filter(Boolean).join(" \xB7 ");return e.id===r?l`<li aria-current="true" tabindex="-1" data-current-package>
        <strong>${n}</strong>${d?` \xB7 ${d}`:""}
      </li>`:l`<li>
      <button
        type="button"
        class="link-btn"
        aria-label=${m(s.showPackage,{name:n})}
        aria-disabled=${this._busy?"true":"false"}
        @click=${()=>this._switchTo(e.id)}
      >
        ${n}</button
      >${d?` \xB7 ${d}`:""}
    </li>`}_renderTimeline(e){if(!e.length)return l`<p class="muted">${s.noTimeline}</p>`;let r=this.locale;return l`<ol class="timeline">
      ${ms(e).map(i=>{let n=G(i.status),o=i.label.trim(),a=[j(i.time,r),Nt(i.source)].filter(Boolean).join(" \xB7 ");return l`<li style=${F({"--dot-color":Le(i.status)})}>
          <span class="dot" aria-hidden="true"></span>
          <div class="entry-title">${n}</div>
          ${o&&o!==n?l`<div>${o}</div>`:u}
          ${a?l`<div class="entry-meta">${a}</div>`:u}
        </li>`})}
    </ol>`}_renderDateForm(){let e=this._dateForm,r=this._formError,i=(n,o,a,d=!1)=>{let c=r?.field===n;return l`<label class="field">
        <span class="field-label">${o}</span>
        <input
          type=${a}
          name=${n}
          .value=${C(e[n])}
          ?data-first=${d}
          aria-invalid=${c?"true":"false"}
          aria-describedby=${c?"date-error":u}
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
    </form>`}_renderMerge(e){let{pool:r,shown:i,target:n}=this._mergeChoice(e),o=r.likely.length+r.older.length;if(!o)return l`<p class="empty">${s.noMergeCandidates}</p>`;let a=this._mergeQuery.trim()!=="",d=o>hs,c=this._mergeOlder&&!a?r.likely.length:-1,h=!a&&!this._mergeOlder&&r.older.length>0;return l`<p id="merge-intro">${s.mergeIntro}</p>
      ${d?l`<label class="field">
            <span class="field-label">${s.mergeSearch}</span>
            <input
              type="search"
              data-first
              autocomplete="off"
              placeholder=${s.mergeSearchPlaceholder}
              .value=${C(this._mergeQuery)}
              @input=${this._onMergeQuery}
            />
          </label>`:u}
      <fieldset class="merge-list" aria-describedby="merge-intro">
        <legend class="sr-only">${s.mergeChoose}</legend>
        ${i.map((f,p)=>this._renderCandidate(f,{checked:f.id===n,first:!d&&p===0,olderFirst:p===c}))}
        ${a&&!i.length?l`<p class="empty">${s.mergeNoMatch}</p>`:u}
      </fieldset>
      ${h?l`<button
            type="button"
            class="link-btn"
            ?data-first=${!d&&!i.length}
            @click=${this._showOlderMerge}
          >
            ${m(s.mergeShowOlder,{count:String(r.older.length)})}
          </button>`:u}
      ${this._mergeHint&&!n?l`<p class="hint merge-hint" role="alert">${s.mergeChooseFirst}</p>`:u}`}_renderCandidate(e,r){let i=he(e,this.locale);return l`<label class="merge-option">
      <input
        type="radio"
        name="merge-target"
        value=${e.id}
        .checked=${C(r.checked)}
        ?data-first=${r.first}
        ?data-older-first=${r.olderFirst}
        @change=${this._onMergeTarget}
      />
      <span class="merge-lines">
        <span class="merge-line"><strong>${i.title}</strong> · ${i.when}</span>
        <span class="merge-line muted">${i.carrier}</span>
        <span class="merge-line items ${i.items?"":"muted"}">
          ${i.items??s.itemsNotKnown}
        </span>
      </span>
    </label>`}_renderSplit(){let e=this._details?.origins??[],r=this.locale;return l`<fieldset aria-describedby="split-hint">
        <legend>${s.splitIntro}</legend>
        ${e.map((i,n)=>{let o=i.time?j(i.time,r):"";return l`<label class="check-row">
            <input
              type="checkbox"
              .value=${i.id}
              .checked=${C(this._splitSelection.includes(i.id))}
              ?data-first=${n===0}
              @change=${this._onSplitChange}
            />
            <span>
              ${i.label.trim()||Nt(i.source)}${o?l`<span class="muted"> · ${o}</span>`:u}
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
        </div>`}case"split":{let n=Lt(this._splitSelection,this._details?.origins.length??0);return l`<div class="dialog-actions">
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
          ${Li(e,this.snapshot?.settings.user_is_admin===!0)?l`<button
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
          ${pe(e.status)?l`<span class="spacer"></span>
                <button
                  type="button"
                  class="btn primary"
                  aria-disabled=${r}
                  @click=${this._markDelivered}
                >
                  <ha-icon icon="mdi:check" aria-hidden="true"></ha-icon>${s.markDelivered}
                </button>`:u}
        </div>`}}}_setMode(e){this._mode=e,this._error=null,this._formError=null,this.focusAfterRender(e==="archive"?"[data-cancel]":"[data-first], [data-cancel]")}_backToView(){let e=this._mode;this._mode="view",this._error=null,this._formError=null,this.focusAfterRender(`[data-mode="${e}"]`)}_editDate(){let e=this._parcel;this._dateForm=e?Qr(e):Hi,this._setMode("date")}_startMerge(){this._mergeTarget="",this._mergeQuery="",this._mergeOlder=!1,this._mergeHint=!1,this._setMode("merge")}_startSplit(){this._splitSelection=[],this._setMode("split")}_startArchive(){this._setMode("archive")}_parcelService(e,r,i){let n=this.hass,o=this._parcel;!n||!o||this.runAction(()=>Z(n,e,{parcel_id:o.id,...r}),i)}_confirm(){this._parcelService("update",{confirm:!0})}_undoMerge(){this._parcelService("undo_merge",{})}_keepMerge(){this._parcelService("update",{confirm_merge:!0})}_undoInferred(){this._parcelService("undo_delivery",{})}_keepInferred(){this._parcelService("update",{confirm_delivery:!0})}_markDelivered(){this._parcelService("mark_delivered",{})}async _checkAgain(){let e=this.hass,r=this._parcel;if(!e||!r||this._busy)return;let i=++this._checkRun,n=Wt(null);this._checkStatus=null,this._checking=!0,await this.runAction(async()=>{let o=await J(e,"parcel/check_again",{parcel_id:r.id});n=Wt(o)},()=>{let o=this.snapshot?.settings;this._checkStatus=Di(n,{enabled:o?.ai_enabled===!0,mode:o?.ai_mode??"off"})}),i===this._checkRun&&(this._checking=!1)}_dismissCheckStatus(){this._checkStatus=null}_archive(){this._parcelService("archive",{},()=>this.closeDialog())}_onPrivateClick(e){this._busy&&e.preventDefault()}_togglePrivate(e){let r=e.currentTarget.checked,i=this.hass,n=this._parcel;!i||!n||this._busy||(this._pendingPrivate=r,this.runAction(async()=>{try{await Z(i,"update",{parcel_id:n.id,private:r})}catch(o){throw this._pendingPrivate=null,o}}))}_onDateInput(e){let r=e.currentTarget,i=r.name;this._dateForm={...this._dateForm,[i]:r.value},this._formError=null}_saveDate(e){e.preventDefault();let r=this._parcel;if(!r||this._busy)return;let i=this._dateForm,n=tt(i);if(n){this._formError=n,this.focusAfterRender(`[name="${n.field}"]`);return}let o=Zr(r.id,i);this._parcelService("update",o,()=>this._backToView())}_mergePool(e){let r=this.snapshot;return r?fi(r.parcels,e,{today:r.settings.today,timeZone:r.settings.time_zone}):{likely:[],older:[]}}_mergeChoice(e){let r=this._mergePool(e),i=this._mergeQuery.trim(),n=r.likely;i?n=gi([...r.likely,...r.older],i):this._mergeOlder&&(n=[...r.likely,...r.older]);let o=n.some(a=>a.id===this._mergeTarget)?this._mergeTarget:"";return{pool:r,shown:n,target:o}}_onMergeTarget(e){this._mergeTarget=e.currentTarget.value,this._mergeHint=!1}_onMergeQuery(e){this._mergeQuery=e.currentTarget.value}_showOlderMerge(){this._mergeOlder=!0,this.focusAfterRender("[data-older-first]")}_acceptPossible(e){let r=this.hass;if(!r)return;let i=null;this.runAction(async()=>{let n=await J(r,"suggestion/accept",{suggestion_id:e.suggestionId,parcel_id:e.candidateId});i=typeof n?.parcel_id=="string"?n.parcel_id:null},()=>{i!==null&&i!==this._parcelId&&(this._parcelId=i,this._details=null,this._loadError=null,this._load()),this.focusAfterRender("[data-autofocus]")})}_dismissPossible(e){let r=this.hass;r&&this.runAction(()=>J(r,"suggestion/dismiss",{suggestion_id:e.suggestionId,parcel_id:e.candidateId}),()=>{this.focusAfterRender("[data-autofocus]")})}_merge(){let e=this.hass,r=this._parcel;if(!e||!r)return;let{target:i}=this._mergeChoice(r);if(!i){this._mergeHint=!0,this.focusAfterRender('input[name="merge-target"]');return}this.runAction(()=>Z(e,"merge",{parcel_ids:[r.id,i]}),()=>this._backToView())}_onSplitChange(e){let r=e.currentTarget,i=this._splitSelection.filter(n=>n!==r.value);this._splitSelection=r.checked?[...i,r.value]:i}_split(){let e=this._details?.origins.length??0;Lt(this._splitSelection,e)&&this._parcelService("split",{origins:[...this._splitSelection]},()=>this._backToView())}async _copy(e){let r=e.currentTarget,i=this._parcel?.tracking_number?.trim();if(!i)return;this._copyState="idle";try{if(!navigator.clipboard?.writeText)throw new Error("Clipboard API unavailable");await navigator.clipboard.writeText(i),this._copyState="copied";return}catch{}let n=this.renderRoot.querySelector("#tracking-number");n?.focus(),n?.select();let o=!1;try{o=document.execCommand("copy")}catch{o=!1}this._copyState=o?"copied":"failed",o&&r.focus()}};B("parcels-details-dialog",Gt);var Vt=["all","active","recent","completed"],mt={all:s.filterAll,active:s.filterActive,recent:s.filterRecent,completed:s.filterCompleted},ft="parcels-filter",gt="parcels-filter-changed";function Qt(t){return typeof t=="string"&&Vt.includes(t)}function Ui(){try{return globalThis.localStorage??null}catch{return null}}function _t(t=Ui()){try{let e=t?.getItem(ft);return Qt(e)?e:"all"}catch{return"all"}}function Bi(t,e=Ui(),r=globalThis.window??null){try{e?.setItem(ft,t)}catch{}r?.dispatchEvent(new CustomEvent(gt,{detail:t}))}function fs(t,{today:e,timeZone:r}){let i=et(e),n=ee(i,6),o=d=>d!==null&&w(d,i)>=0&&w(d,n)<=0;if(o(E(t.status_time,r))||o(E(t.delivered_at,r)))return!0;let a=k(t);return a!==null&&w(a.start,n)<=0&&w(a.end,i)>=0}function zi(t,e,r){switch(e){case"active":return pe(t.status);case"completed":return!pe(t.status);case"recent":return fs(t,r);default:return!0}}var gs="parcels/subscribe",ji=[2e3,1e4,3e4,6e4,3e5],bt=new Map,_s=0;function Wi(t,e){try{t(e)}catch(r){console.error(r)}}function Ki(t,e){t.state=e;for(let r of[...t.listeners.values()])Wi(r,e)}function qi(t){try{t().catch(()=>{})}catch{}}function yt(t){t.retryTimer!==void 0&&(clearTimeout(t.retryTimer),t.retryTimer=void 0)}function vt(t){t.connection.removeEventListener("ready",t.onReady),t.connection.removeEventListener("disconnected",t.onDisconnected)}function bs(t){yt(t);let e=ji[Math.min(t.retries,ji.length-1)]??3e5;t.retries+=1,t.retryTimer=setTimeout(()=>{t.retryTimer=void 0,Zt(t)},e)}function Zt(t){if(t.released||t.unsubscribe||t.pending||t.listeners.size===0)return;yt(t);let e=++t.attempt,r=t.epoch,i=()=>!t.released&&t.attempt===e;t.pending=!0;let n;try{n=t.connection.subscribeMessage(o=>{i()&&(t.retries=0,Ki(t,{snapshot:Oi(o),error:null}))},{type:gs},{resubscribe:!1})}catch(o){n=Promise.reject(o)}n.then(o=>{if(i()){t.pending=!1,t.unsubscribe=o;return}t.epoch===r&&qi(o),t.released&&t.attempt===e+1&&(t.pending=!1,vt(t))},o=>{i()?(t.pending=!1,Ki(t,{snapshot:t.state.snapshot,error:I(o)}),bs(t)):t.released&&t.attempt===e+1&&(t.pending=!1,vt(t))})}function vs(t,e){if(!t.listeners.delete(e)||t.listeners.size>0)return;t.released=!0,t.attempt+=1,yt(t),bt.get(t.connection)===t&&bt.delete(t.connection);let r=t.unsubscribe;t.unsubscribe=null,r&&qi(r),t.pending||vt(t)}function ys(t){let e={connection:t,listeners:new Map,state:{snapshot:null,error:null},epoch:0,attempt:0,unsubscribe:null,pending:!1,released:!1,retries:0,retryTimer:void 0,onReady:()=>{e.released||e.unsubscribe||(e.pending=!1,e.retries=0,Zt(e))},onDisconnected:()=>{e.epoch+=1,e.attempt+=1,e.unsubscribe=null,e.pending=!1,yt(e),e.released&&vt(e)}};return e}function Yi(t,e){let r=++_s,i=bt.get(t);i?(i.listeners.set(r,e),(i.state.snapshot||i.state.error)&&Wi(e,i.state)):(i=ys(t),bt.set(t,i),i.listeners.set(r,e),t.addEventListener("ready",i.onReady),t.addEventListener("disconnected",i.onDisconnected),Zt(i));let n=i,o=!0;return()=>{o&&(o=!1,vs(n,r))}}var $t=class{snapshot=null;error=null;_host;_connection=null;_unsubscribe=null;_hostConnected=!1;constructor(e){this._host=e,e.addController(this)}setConnection(e){e!==this._connection&&(this._release(),this._connection=e,this.snapshot=null,this.error=null,this._hostConnected&&this._subscribe(),this._host.requestUpdate())}hostConnected(){this._hostConnected=!0,this._subscribe()}hostDisconnected(){this._hostConnected=!1,this._release()}_subscribe(){!this._connection||this._unsubscribe||(this._unsubscribe=Yi(this._connection,e=>{this.snapshot=e.snapshot??this.snapshot,this.error=e.error,this._host.requestUpdate()}))}_release(){let e=this._unsubscribe;this._unsubscribe=null,e?.()}};var Fe=class extends D{static properties={_actionError:{state:!0}};_snapshots=new $t(this);_hass=void 0;_hassKey=null;_locale=null;_localeKey="";constructor(){super(),this._actionError=null}get hass(){return this._hass}set hass(e){this._hass=e,this._snapshots.setConnection(e?.connection??null),this.toggleAttribute("dark",e?.themes?.darkMode===!0);let r=JSON.stringify([e?.language,e?.locale?.language,e?.locale?.time_format,e?.locale?.time_zone,e?.config?.time_zone,e?.user?.is_admin,e?.themes?.darkMode]);r!==this._hassKey&&(this._hassKey=r,this.requestUpdate()),this.hassChanged()}hassChanged(){}get snapshot(){return this._snapshots.snapshot}get locale(){let e=this._snapshots.snapshot?.settings.time_zone,r=`${this._hassKey??""}|${e??""}`;return(!this._locale||r!==this._localeKey)&&(this._locale=st(this._hass,e),this._localeKey=r),this._locale}async callService(e,r,i){let n=this._hass;if(!n)return!1;this._actionError=null;try{return await Z(n,e,r),!0}catch(o){return this._actionError=m(i,{message:I(o)}),!1}}renderBanners(){let{snapshot:e,error:r}=this._snapshots;return!r&&!this._actionError?u:l`<div class="banners">
      ${r?l`<div class="alert ${e?"warning":"error"}" role="alert">
            <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              ${m(e?s.refreshError:s.loadError,{message:r})}
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
    </div>`}renderLoading(){return this._snapshots.error?u:l`<p class="empty" role="status">${s.loading}</p>`}showActionError(e){this._actionError=e}_dismissActionError(){this._actionError=null}},ye=class extends Fe{static properties={_busyParcels:{state:!0},_filter:{state:!0}};_focusedParcel=null;constructor(){super(),this._busyParcels=new Set,this._filter=_t()}connectedCallback(){super.connectedCallback(),this._filter=_t(),window.addEventListener(gt,this._onFilterEvent),window.addEventListener("storage",this._onStorage)}disconnectedCallback(){super.disconnectedCallback(),window.removeEventListener(gt,this._onFilterEvent),window.removeEventListener("storage",this._onStorage)}setFilter(e){this._filter=e,Bi(e)}filterParcels(e,r){let i=this._filter;if(i==="all")return r;let n={today:e.settings.today,timeZone:e.settings.time_zone};return r.filter(o=>zi(o,i,n))}_candidates=null;possiblyFor(e){let r=this.snapshot;if(!r)return null;this._candidates?.snapshot!==r&&(this._candidates={snapshot:r,map:_i(r.merge_suggestions)});let i=this._candidates.map,n=new Set(e.map(a=>a.id)),o=new Map;for(let a of e)for(let d of i.get(a.id)??[])n.has(d.id)||o.set(d.id,d);return o.size?Ai([...o.values()]):null}_onFilterEvent=e=>{let r=e.detail;Qt(r)&&(this._filter=r)};_onStorage=e=>{(e.key===null||e.key===ft)&&(this._filter=_t())};willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement;this._focusedParcel=r instanceof HTMLElement?r.closest(".chip[data-parcel-id]")?.dataset.parcelId??null:null}updated(e){super.updated(e);let r=this._focusedParcel;this._focusedParcel=null,r!==null&&!this.shadowRoot?.activeElement&&Jt()&&this.renderRoot.querySelector(Kt(r))?.focus()}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback], button.chip-main")}openDetails=(e,r)=>{this.renderRoot.querySelector("parcels-details-dialog")?.open(e.id,()=>{(r.isConnected?r:this.renderRoot.querySelector(Kt(e.id))??this.focusFallback())?.focus()})};undoMerge=e=>{this._parcelAction(e.id,"undo_merge",{parcel_id:e.id},s.undoFailed)};keepMerge=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_merge:!0},s.keepFailed)};undoInferred=e=>{this._parcelAction(e.id,"undo_delivery",{parcel_id:e.id},s.undoInferredFailed)};keepInferred=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_delivery:!0},s.keepInferredFailed)};renderDetailsDialog(){return l`<parcels-details-dialog
      .hass=${this.hass}
      .snapshot=${this.snapshot}
      .locale=${this.locale}
      @parcels-error=${this._onDialogError}
    ></parcels-details-dialog>`}async _parcelAction(e,r,i,n){if(!this._busyParcels.has(e)){this._busyParcels=new Set([...this._busyParcels,e]);try{await this.callService(r,i,n)}finally{let o=new Set(this._busyParcels);o.delete(e),this._busyParcels=o}}}_onDialogError(e){this.showActionError(e.detail)}};function Jt(){let t=document.activeElement;return!t||t===document.body}function Xt(t){if(typeof t!="object"||t===null||Array.isArray(t))throw new Error(s.configInvalid);return t}function er(t){let e=t.title;if(e!=null){if(typeof e!="string")throw new Error(s.configTitle);return e.trim()}}function tr(t){return typeof t.type=="string"?t.type:""}function rr(t){let e=Xt(t),r=e.show_archived??!0;if(typeof r!="boolean")throw new Error(s.configShowArchived);return{type:tr(e),title:er(e),show_archived:r}}function ir(t){let e=Xt(t);return{type:tr(e),title:er(e)}}function nr(t){let e=Xt(t);return{type:tr(e),title:er(e)}}function $e(t,e){return t===void 0?e:t||null}function $s(t,e){let r=E(t.status_time,e.timeZone);switch(t.status){case"cancelled":return null;case"delivered":{let n=E(t.delivered_at,e.timeZone)??r;return n?{kind:"delivered",from:n,to:n}:null}case"returned":return r?{kind:"returned",from:r,to:r}:null;case"ready_for_pickup":{let n=r??e.today;return{kind:"pickup",from:n,to:Gr(n,e.today)}}default:break}let i=k(t);return i?{kind:"eta",from:i.start,to:i.end}:(t.status==="attempted"||t.status==="exception")&&r?{kind:"status",from:r,to:r}:null}function Gi(t){return t.window_start??t.window_end??"~"}function sr(t,e){return t<e?-1:t>e?1:0}function ws(t,e){return t.startCol-e.startCol||e.endCol-e.startCol-(t.endCol-t.startCol)||sr(Gi(t.parcel),Gi(e.parcel))||sr(L(t.parcel).toLowerCase(),L(e.parcel).toLowerCase())||sr(t.parcel.id,e.parcel.id)}function Vi(t,e,r,i){let n=Yr(e),o=ee(e,6),a=[];for(let f of t){if(f.archived&&!i.showArchived)continue;let p=$s(f,r);!p||w(p.to,e)<0||w(p.from,o)>0||a.push({parcel:f,members:[f],placement:p,startCol:Math.max(0,ce(e,p.from)),endCol:Math.min(6,ce(e,p.to)),continuesBefore:w(p.from,e)<0,continuesAfter:w(p.to,o)>0,lane:0})}let d=zt(a,f=>jt(f.parcel,f.placement.kind,f.placement.from,f.placement.to)).map(f=>({...f.reduce((g,_)=>ve(_.parcel,g.parcel)<0?_:g),members:f.map(g=>g.parcel).sort(ve)}));d.sort(ws);let c=[];for(let f of d){let p=c.findIndex(g=>g<f.startCol);p===-1&&(p=c.length),c[p]=f.endCol,f.lane=p}let h=n.map((f,p)=>d.filter(g=>g.startCol<=p&&p<=g.endCol).sort((g,_)=>g.lane-_.lane));return{start:e,end:o,days:n,items:d,lanes:c.length,perDay:h,busy:h.map(f=>f.length>0)}}var xs=600,ks=616,Ss={weekday:"short"},Ts={day:"numeric"},As={weekday:"long",day:"numeric",month:"long"},Cs={weekday:"long",day:"numeric",month:"short"},or=class extends ye{static properties={_config:{state:!0},_weekOffset:{state:!0},_narrow:{state:!0},_refreshing:{state:!0}};static styles=[z,rt,x`
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
    `];_resizeObserver=null;_resizeFrame=0;_layoutCache=null;constructor(){super(),this._config=rr({}),this._weekOffset=0,this._narrow=!1,this._refreshing=!1}static getStubConfig(){return{}}setConfig(e){this._config=rr(e)}getCardSize(){let e=this._layout();return e?this._narrow?9+e.perDay.reduce((i,n)=>i+n.length,0):3+Math.max(1,e.lanes):4}getGridOptions(){return{columns:"full",rows:"auto",min_columns:6}}connectedCallback(){super.connectedCallback(),typeof ResizeObserver<"u"&&(this._resizeObserver??=new ResizeObserver(e=>{let r=e[e.length-1]?.contentRect.width??0;cancelAnimationFrame(this._resizeFrame),this._resizeFrame=requestAnimationFrame(()=>this._measure(r))}),this._resizeObserver.observe(this))}disconnectedCallback(){super.disconnectedCallback(),this._resizeObserver?.disconnect(),cancelAnimationFrame(this._resizeFrame)}firstUpdated(e){super.firstUpdated(e),this._measure(this.getBoundingClientRect().width)}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback]")}_measure(e){e<=0||(e<xs?this._narrow=!0:e>=ks&&(this._narrow=!1))}_monday(e){return ee(et(e.settings.today),7*this._weekOffset)}_layout(){let e=this.snapshot;if(!e)return null;let r=this._monday(e),i=this._config.show_archived,n=this._filter,o=this._layoutCache;if(o&&o.snapshot===e&&o.monday===r&&o.showArchived===i&&o.filter===n)return o.layout;let a=Vi(this.filterParcels(e,e.parcels),r,{today:e.settings.today,timeZone:e.settings.time_zone},{showArchived:i});return this._layoutCache={snapshot:e,monday:r,showArchived:i,filter:n,layout:a},a}render(){let e=this.snapshot,r=this._layout(),i=$e(this._config.title,s.defaultWeekTitle),n=r?R(r.start,r.end,this.locale,ni):"";return l`<ha-card>
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
      ${this.renderDetailsDialog()}
      <parcels-add-dialog
        .hass=${this.hass}
        @parcels-error=${this._onAddError}
      ></parcels-add-dialog>`}_renderGrid(e,r,i){let n=this.locale,o=e.settings.today,a=r.items.length===0,c={"grid-template-columns":r.busy.map(h=>h||a?"minmax(0, 1fr)":"minmax(0, 0.6fr)").join(" "),"grid-template-rows":`auto repeat(${Math.max(1,r.lanes)}, auto)`};return l`<div
      class="grid"
      role="group"
      aria-label=${m(s.weekOf,{range:i})}
      style=${F(c)}
    >
      ${r.days.map((h,f)=>l`<div
            class="day-bg ${h===o?"today":""}"
            style=${F({"grid-column":String(f+1)})}
            aria-hidden="true"
          ></div>`)}
      ${r.days.map((h,f)=>l`<div
            class="day-head ${h===o?"today":""}"
            style=${F({"grid-column":String(f+1)})}
            aria-current=${h===o?"date":u}
          >
            <span class="dow" aria-hidden="true">${ue(h,n,Ss)}</span>
            <span class="dom" aria-hidden="true">${ue(h,n,Ts)}</span>
            <span class="sr-only">${ue(h,n,As)}</span>
          </div>`)}
      ${a?l`<p class="week-empty">${this._emptyText()}</p>`:u}
      ${q(r.items,h=>h.parcel.id,h=>this._chip(h,!1,{"grid-column":`${h.startCol+1} / ${h.endCol+2}`,"grid-row":String(h.lane+2)}))}
    </div>`}_renderStacked(e,r,i){let n=this.locale,o=e.settings.today,a=this._filter!=="all"&&r.items.length===0;return l`${a?l`<p class="week-empty stacked">${this._emptyText()}</p>`:u}
      <ol class="days" aria-label=${m(s.weekOf,{range:i})}>
      ${r.days.map((d,c)=>{let h=r.perDay[c]??[],f=d===o;return l`<li
          class="day ${h.length?"":"compact"} ${f?"today":""}"
          aria-current=${f?"date":u}
        >
          <p class="day-label">
            ${ue(d,n,Cs)}${f?l`<span class="badge info">${s.todayTag}</span>`:u}
          </p>
          ${h.length?l`<ul class="day-chips">
                ${q(h,p=>p.parcel.id,p=>l`<li>${this._chip(p,!0,void 0,c)}</li>`)}
              </ul>`:l`<span class="muted">${s.noDeliveriesThisDay}</span>`}
        </li>`})}
    </ol>`}_chip(e,r,i,n){let o=e.continuesBefore&&(!r||n===e.startCol),a=e.continuesAfter&&(!r||n===e.endCol);return ct(e.parcel,{locale:this.locale,placement:e.placement,continuesBefore:o,continuesAfter:a,showRange:r,members:e.members,possibly:this.possiblyFor(e.members),busy:e.members.some(d=>this._busyParcels.has(d.id)),position:i,onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge,onUndoInferred:this.undoInferred,onKeepInferred:this.keepInferred})}_renderFilters(){return l`<div class="filters" role="group" aria-label=${s.filterLabel}>
      ${Vt.map(e=>l`<button
            type="button"
            class="filter-btn"
            aria-pressed=${this._filter===e?"true":"false"}
            title=${e==="recent"?s.filterRecentHint:u}
            @click=${()=>this.setFilter(e)}
          >
            ${mt[e]}
          </button>`)}
    </div>`}_emptyText(){return this._filter==="all"?s.noDeliveriesThisWeek:s.filterEmptyWeek}_previousWeek(){this._weekOffset-=1}_nextWeek(){this._weekOffset+=1}_thisWeek(){this._weekOffset=0}async _refresh(){if(!this._refreshing){this._refreshing=!0;try{await this.callService("refresh",{},s.refreshFailed)}finally{this._refreshing=!1}}}_openAdd(e){let r=e.currentTarget;this.renderRoot.querySelector("parcels-add-dialog")?.open(()=>{r.isConnected&&r.focus()})}_onAddError(e){this.showActionError(e.detail)}};B("parcels-week-card",or);_e("parcels-week-card",s.weekCardName,s.weekCardDescription);var ar=class extends ye{static properties={_config:{state:!0}};static styles=[z,rt,x`
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
    `];_listCache=null;constructor(){super(),this._config=ir({})}static getStubConfig(){return{}}setConfig(e){this._config=ir(e)}getCardSize(){let e=this._list()?.boxes;return e?1+Math.max(1,e.length):3}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}focusFallback(){return this.renderRoot.querySelector("button.chip-main")??this.renderRoot.querySelector(".content")}_list(){let e=this.snapshot;if(!e)return null;let r=this._filter,i=this._listCache;if(i?.snapshot===e&&i.filter===r)return i;let n=mi(e.parcels),o=this.filterParcels(e,n);return this._listCache={snapshot:e,filter:r,boxes:Ei(o),hidden:n.length-o.length},this._listCache}render(){let e=this._list(),r=$e(this._config.title,s.defaultListTitle);return l`<ha-card>
        ${r?l`<div class="header"><h2 class="title">${r}</h2></div>`:u}
        ${this.renderBanners()}
        <div class="content" tabindex="-1">
          ${e?this._renderList(e.boxes,e.hidden):this.renderLoading()}
        </div>
      </ha-card>
      ${this.renderDetailsDialog()}`}_renderFilterNote(e){return e===0||this._filter==="all"?u:l`<p class="filter-note">
      ${m(s.filterNote,{filter:mt[this._filter]})} ·
      <button type="button" class="link-btn" @click=${this._showAll}>${s.filterShowAll}</button>
    </p>`}_showAll=()=>{this.setFilter("all")};_renderList(e,r){if(!e.length)return l`${this._renderFilterNote(r)}
        <p class="empty">${r>0?s.noUndatedMatch:s.noUndatedParcels}</p>`;let i=this.locale;return l`${this._renderFilterNote(r)}
      <ul class="list">
      ${q(e,n=>n.parcel.id,({parcel:n,members:o})=>l`<li>
            ${ct(n,{locale:i,showStatus:!0,members:o,possibly:this.possiblyFor(o),busy:o.some(a=>this._busyParcels.has(a.id)),onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge,onUndoInferred:this.undoInferred,onKeepInferred:this.keepInferred})}
          </li>`)}
    </ul>`}};B("parcels-list-card",ar);_e("parcels-list-card",s.listCardName,s.listCardDescription);function Es(t,e,r){let i=t.get(e);return i==="pending"||i!==void 0&&i===r}function wt(t,e,r){if(!e.size)return t;let i=t.filter(n=>!Es(e,n.id,r));return i.length===t.length?t:i}function dr(t,e){let r=new Map(t);for(let i of e)r.set(i,"pending");return r}function cr(t,e){let r=new Map(t);for(let i of e)r.delete(i);return r}function ur(t,e,r,i){let n=new Map(t);for(let o of e)r&&i(o)?n.set(o,r):n.delete(o);return n}function Qi(t,e){let r=null;for(let[i,n]of t)n!=="pending"&&n!==e&&(r??=new Map(t),r.delete(i));return r??t}function Zi(t,e){if(t<=0)return null;let r=t===1?s.aiQueueOne:m(s.aiQueueMany,{count:t});if(e===null)return r;let i=Math.max(1,Math.round(e/60));return i<120?m(s.aiQueueMinutes,{queue:r,minutes:i}):m(s.aiQueueHours,{queue:r,hours:Math.round(i/60)})}function lr(t,e,r){return t<=0?null:t===1?e:m(r,{count:t})}function Ji(t){let e=[lr(t.added,s.trustAddedOne,s.trustAddedMany),lr(t.rechecking,s.trustRecheckOne,s.trustRecheckMany),lr(t.kept,s.trustKeptOne,s.trustKeptMany)].filter(r=>r!==null);return e.length?m(s.trustDoneWith,{domain:t.domain,parts:e.join(", ")}):m(s.trustDone,{domain:t.domain})}function Xi(t){let e=[[s.checkHeaders,String(t.headers)]];return t.servers.length&&e.push([s.checkServers,t.servers.map(r=>r||s.checkNoServer).join(", ")]),t.originals>0&&e.push([s.checkOriginals,String(t.originals)]),t.used===null?(e.push([s.checkUsed,s.checkUsedNone]),e):(e.push([s.checkUsed,m(s.checkUsedHeader,{n:t.used+1})],["DKIM",t.dkim||s.checkNoResult],["DMARC",t.dmarc||s.checkNoResult],["SPF",t.spf||s.checkNoResult]),e)}var we=["review","filtered"],Ps=new Set(["not_parcel","unknown"]),Rs={weekday:"short",day:"numeric",month:"short"};function en(t){return N(t.received??t.created)??-1/0}function tn(t){return[...t].sort((e,r)=>en(r)-en(e)||(e.id<r.id?-1:e.id>r.id?1:0))}function Ms(t){return[...t].sort((e,r)=>(r.day??"").localeCompare(e.day??"")||(e.id<r.id?-1:e.id>r.id?1:0))}function pr(t,e){if(!t.has(e))return t;let r=new Map(t);return r.delete(e),r}var hr=class extends Fe{static properties={_config:{state:!0},_tab:{state:!0},_editing:{state:!0},_editForm:{state:!0},_editProblem:{state:!0},_busyItems:{state:!0},_itemErrors:{state:!0},_hidden:{state:!0},_confirmClearAll:{state:!0},_confirmTrust:{state:!0},_trustStatus:{state:!0}};static styles=[z,x`
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
    `];connectedWhileHidden=!0;_focusedItem=null;_listCache=null;_visibleCache=null;_clearingAll=!1;constructor(){super(),this._config=nr({}),this._tab="review",this._editing=null,this._editForm=It(null),this._editProblem=null,this._busyItems=new Set,this._itemErrors=new Map,this._hidden=new Map,this._confirmClearAll=!1,this._confirmTrust=null,this._trustStatus=null}static getStubConfig(){return{}}setConfig(e){this._config=nr(e)}getCardSize(){if(!this._visible())return 0;let e=this._visibleLists();if(!e)return 3;let r=this._tab==="review"?e.review.length+e.suggestions.length:e.filtered.length;return 2+2*Math.max(1,r)}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}hassChanged(){this._syncVisibility()}_visible(){let e=this.snapshot;return e?e.settings.user_is_admin:this.hass?.user?.is_admin===!0}_syncVisibility(){let e=!this._visible();this.hidden!==e&&(this.hidden=e,this.dispatchEvent(new CustomEvent("card-visibility-changed",{bubbles:!0,composed:!0,detail:{value:!e}})))}_lists(){let e=this.snapshot;return e?(this._listCache?.snapshot!==e&&(this._listCache={snapshot:e,review:tn(e.review),suggestions:Ms(e.merge_suggestions),filtered:tn(e.filtered)}),this._listCache):null}_visibleLists(){let e=this._lists();if(!e)return null;let r=this._hidden;if(this._visibleCache?.lists!==e||this._visibleCache.hidden!==r){let i=this.snapshot;this._visibleCache={lists:e,hidden:r,visible:{review:wt(e.review,r,i),suggestions:wt(e.suggestions,r,i),filtered:wt(e.filtered,r,i)}}}return this._visibleCache.visible}_listed(e){let r=this._lists();return r?[...r.review,...r.suggestions,...r.filtered].some(i=>i.id===e):!1}willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement,i=r instanceof HTMLElement?r.closest("[data-item-id]"):null;if(i){let o=[...this.renderRoot.querySelectorAll("[data-item-id]")].filter(a=>!a.closest("[hidden]"));this._focusedItem={id:i.dataset.itemId??"",index:o.indexOf(i)}}else this._focusedItem=null;this._hidden=Qi(this._hidden,this.snapshot),this._confirmClearAll&&!this._visibleLists()?.filtered.length&&(this._confirmClearAll=!1,r instanceof HTMLElement&&r.closest(".confirm")&&this._focusAfterUpdate("#panel-filtered"));let n=this._lists();if(n){let o=new Set([...n.review,...n.suggestions,...n.filtered].map(a=>a.id));this._editing!==null&&!o.has(this._editing)&&(this._editing=null,this._editProblem=null);for(let a of this._itemErrors.keys())o.has(a)||(this._itemErrors=pr(this._itemErrors,a))}}updated(e){super.updated(e),this._syncVisibility();let r=this._focusedItem;if(this._focusedItem=null,!r||this.shadowRoot?.activeElement||!Jt())return;let n=[...this.renderRoot.querySelector(`#panel-${this._tab}`)?.querySelectorAll("[data-item-id]")??[]];(n.find(a=>a.dataset.itemId===r.id)??n[Math.min(Math.max(r.index,0),n.length-1)]??this.renderRoot.querySelector(`#tab-${this._tab}`))?.focus()}render(){if(!this._visible())return u;let e=this._visibleLists(),r=$e(this._config.title,s.defaultReviewTitle);return l`<ha-card>
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
    </ha-card>`}_renderTabs(e,r){let i=n=>m(s.tabCount,{label:n==="review"?s.tabReview:s.tabFiltered,count:n==="review"?e:r});return l`<div
      class="tabs"
      role="tablist"
      aria-label=${s.reviewTabs}
      @keydown=${this._onTabKeyDown}
    >
      ${we.map(n=>{let o=this._tab===n;return l`<button
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
    </div>`}_renderReviewList(e,r){let i=this.snapshot?.settings,n=i?Zi(i.ai_queue,i.ai_queue_seconds):null,o=n?l`<p class="hint queue-hint">${n}</p>`:u,a=l`<div class="trust-status" role="status">
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
      ${q(r,d=>d.id,(d,c)=>this._renderMergeSuggestion(d,c))}
      ${q(e,d=>d.id,(d,c)=>this._renderReviewItem(d,c))}
    </div>`}_renderMergeSuggestion(e,r){let i=this.locale,o=this._busyItems.has(e.id)?"true":"false",a=`suggestion-subject-${r}`,d=Oe(e.parcel,i),c=ot(e.reason),h=this.snapshot?.settings,f=h?[...e.candidates].sort(Ut(e.parcel,{today:h.today,timeZone:h.time_zone})):e.candidates;return l`<article
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
        ${m(s.suggestionTitle,{parcel:he(e.parcel,i).title})}
      </h3>
      <p class="subject-lines">${this._renderLines(e.parcel)}</p>
      ${c?l`<p class="meta">${m(s.reasonIs,{reason:c})}</p>`:u}
      <p class="hint">${s.suggestionHint}</p>
      <ul class="candidates">
        ${f.map(p=>{let g=Oe(p,i);return l`<li class="candidate">
            <span class="grow">${this._renderLines(p)}</span>
            <button
              type="button"
              class="btn"
              aria-label=${m(s.mergeSuggestedLabel,{candidate:g,title:d})}
              aria-disabled=${o}
              @click=${()=>this._command(e.id,"suggestion/accept",{suggestion_id:e.id,parcel_id:p.id})}
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
          aria-label=${m(s.keepApartLabel,{title:d})}
          aria-disabled=${o}
          @click=${()=>this._command(e.id,"suggestion/dismiss",{suggestion_id:e.id})}
        >
          ${s.keepApart}
        </button>
      </div>
    </article>`}_renderLines(e){let r=he(e,this.locale);return l`<span class="block"><strong>${r.title}</strong> · ${r.when}</span>
      <span class="meta block">${r.carrier}</span>
      <span class="meta block items-line">${r.items??s.itemsNotKnown}</span>`}_renderFilteredList(e){return l`<p class="hint filtered-hint">${s.filteredHint}</p>
      ${e.length?l`${this._renderClearAll()}
            <div class="items">
            ${q(e,r=>r.id,(r,i)=>this._renderFilteredItem(r,i))}
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
      </div>`}_renderHead(e,r,i=u){return l`<div class="item-head">
        <span class="sender">${e.sender||e.sender_domain}</span>${i}
      </div>
      <h3 class="subject" id=${r}>${e.subject.trim()||s.noSubject}</h3>`}_renderError(e){let r=this._itemErrors.get(e);return r?l`<div class="alert error" role="alert">
          <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
          <span class="grow">${r}</span>
        </div>`:u}_renderReviewItem(e,r){let i=this.locale,n=this._busyItems.has(e.id),o=this._editing===e.id,a=`review-subject-${r}`,d=e.received??e.created,c=oi(e.reason),h=[d?m(s.receivedOn,{date:j(d,i)}):"",e.mailbox_owner?m(s.mailboxOf,{owner:e.mailbox_owner}):"",c?m(s.reasonIs,{reason:c}):""].filter(Boolean),f=e.source==="ai"?l`<span class="badge ai" title=${s.aiSuggestionLabel}>
            ${s.aiBadge}<span class="sr-only">, ${s.aiSuggestionLabel}</span>
          </span>`:u;return l`<article
      class="item"
      tabindex="-1"
      data-item-id=${e.id}
      aria-labelledby=${a}
      aria-busy=${n?"true":"false"}
    >
      ${this._renderHead(e,a,f)}
      ${h.length?l`<p class="meta">${h.join(" \xB7 ")}</p>`:u}
      ${e.authenticated?u:l`<div class="alert warning">
            <ha-icon icon="mdi:shield-alert-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              <strong class="block">${s.unverifiedSender}</strong>
              ${e.trusted_sender?m(s.trustedSenderNote,{domain:e.sender_domain||e.sender}):s.unverifiedSenderHint}
            </span>
          </div>`}
      ${e.checks?this._renderChecks(e.checks):u}
      ${o?this._renderEditForm(e,n):this._renderSuggestion(e.suggestion)}
      ${this._renderError(e.id)} ${o?u:this._renderReviewActions(e,n)}
    </article>`}_renderChecks(e){return l`<details class="checks">
      <summary>${s.senderChecks}</summary>
      <dl class="facts">
        ${Xi(e).map(([r,i])=>l`<dt>${r}</dt><dd>${i}</dd>`)}
      </dl>
    </details>`}_renderSuggestion(e){if(!e)return l`<p class="hint section-label">${s.noSuggestion}</p>`;let r=this.locale,i=k(e),n=[[s.fieldKind,Ft(e.kind)||null],[s.fieldMerchant,e.merchant],[s.fieldCarrier,M({carrier:e.carrier,carrier_name:null})],[s.fieldTrackingNumbers,e.tracking_numbers.join(", ")||null],[s.fieldOrderNumbers,e.order_numbers.join(", ")||null],[s.expected,i?R(i.start,i.end,r,Rs):null],[s.timeWindow,be(e.window_start,e.window_end,r)],[s.pickupPoint,e.pickup_point],[s.pickupCode,e.pickup_code],[s.items,e.items.length?l`<ul>
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
            title=${m(s.trustSenderHint,{domain:n})}
            aria-disabled=${i}
            aria-expanded=${e.authenticated?u:this._confirmTrust===e.id?"true":"false"}
            @click=${()=>this._askTrust(e)}
          >
            ${s.trustSender}
          </button>`}
      <button
        type="button"
        class="btn danger"
        title=${m(s.ignoreSenderHint,{domain:n})}
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
      <p id=${n}>${m(s.trustQuestion,{domain:r})}</p>
      <div class="row-actions">
        <button
          type="button"
          class="btn danger primary"
          aria-disabled=${i?"true":"false"}
          @click=${()=>{this._trust(e)}}
        >
          ${m(s.trustConfirm,{domain:r})}
        </button>
        <button type="button" class="btn" data-trust-cancel @click=${()=>this._cancelTrust(e.id)}>
          ${s.cancel}
        </button>
      </div>
    </div>`}_renderEditForm(e,r){let i=this._editForm,n=this._editProblem,o=Object.keys(Qe).filter(c=>!Ps.has(c)||c===i.kind);o.includes(i.kind)||o.unshift(i.kind);let a=Ve();i.carrier&&!Object.hasOwn(X,i.carrier)&&a.unshift({id:i.carrier,name:i.carrier});let d=(c,h,f="text",p)=>{let g=n?.field===c,_=[g?"edit-error":"",p??""].filter(Boolean).join(" ");return l`<label class="field">
        <span class="field-label">${h}</span>
        <input
          type=${f}
          name=${c}
          autocomplete="off"
          .value=${C(i[c])}
          aria-invalid=${g?"true":"false"}
          aria-describedby=${_||u}
          @input=${this._onEditInput}
        />
      </label>`};return l`<form id="edit-form" class="edit-form" novalidate @submit=${this._submitEdit}>
      <div class="form-grid">
        <label class="field">
          <span class="field-label">${s.fieldKind}</span>
          <select name="kind" data-first @change=${this._onEditInput}>
            ${o.map(c=>l`<option value=${c} ?selected=${c===i.kind}>
                  ${Ft(c)||c}
                </option>`)}
          </select>
        </label>
        ${d("merchant",s.fieldMerchant)}
        <label class="field">
          <span class="field-label">${s.fieldCarrier}</span>
          <select name="carrier" @change=${this._onEditInput}>
            <option value="" ?selected=${i.carrier===""}>${s.carrierUnknown}</option>
            ${a.map(c=>l`<option value=${c.id} ?selected=${c.id===i.carrier}>
                  ${c.name}
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
            .value=${C(i.items)}
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
            ${m(s.receivedOn,{date:j(n,this.locale)})}
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
    </article>`}_selectTab(e,r){this._tab=e,r&&this.updateComplete.then(()=>this.renderRoot.querySelector(`#tab-${e}`)?.focus())}_onTabClick(e){let r=e.currentTarget.dataset.tab;this._selectTab(r,!1)}_onTabKeyDown(e){let r=we.indexOf(this._tab),i=getComputedStyle(e.currentTarget).direction==="rtl",n;switch(e.key){case"ArrowRight":n=r+(i?-1:1);break;case"ArrowLeft":n=r+(i?1:-1);break;case"Home":n=0;break;case"End":n=we.length-1;break;default:return}e.preventDefault();let o=we[(n+we.length)%we.length];o&&this._selectTab(o,!0)}_focusAfterUpdate(e){this.updateComplete.then(()=>this.renderRoot.querySelector(e)?.focus())}_askClearAll(){this._confirmClearAll=!0,this._focusAfterUpdate("#clear-all-cancel")}_cancelClearAll(){this._confirmClearAll=!1,this._focusAfterUpdate("#clear-all")}_onConfirmKeyDown(e){e.key==="Escape"&&(e.preventDefault(),e.stopPropagation(),this._cancelClearAll())}async _clearAll(){let e=this.hass,r=this._visibleLists()?.filtered.map(i=>i.id)??[];if(!(!e||this._clearingAll||!r.length)){this._clearingAll=!0,this._confirmClearAll=!1,this._hidden=dr(this._hidden,r),this._focusAfterUpdate("#panel-filtered");try{await J(e,"filtered/clear_all"),this._hidden=ur(this._hidden,r,this.snapshot,i=>this._listed(i))}catch(i){this._hidden=cr(this._hidden,r),this.showActionError(m(s.actionFailed,{message:I(i)}))}finally{this._clearingAll=!1}}}_focusInItem(e,r){this.updateComplete.then(()=>{let i=this.renderRoot.querySelector(`[data-item-id="${CSS.escape(e)}"]`);(i?.querySelector(r)??i)?.focus()})}_startEdit(e){this._busyItems.has(e.id)||(this._editing=e.id,this._editForm=It(e.suggestion),this._editProblem=null,this._itemErrors=pr(this._itemErrors,e.id),this._focusInItem(e.id,"[data-first]"))}_cancelEdit(e){this._editing=null,this._editProblem=null,this._focusInItem(e,"[data-edit]")}_onEditInput(e){let r=e.currentTarget,i=r.name;this._editForm={...this._editForm,[i]:r.value},this._editProblem=null}_submitEdit(e){e.preventDefault();let r=this._editing;if(r===null||this._busyItems.has(r))return;let i=tt(this._editForm);if(i){this._editProblem=i,this._focusInItem(r,`[name="${i.field}"]`);return}this._command(r,"review/accept",{review_id:r,overrides:Xr(this._editForm)},{onSuccess:()=>{this._editing===r&&(this._editing=null)}})}_accept(e){this._command(e.id,"review/accept",{review_id:e.id})}_askTrust(e){if(!this._busyItems.has(e.id)){if(e.authenticated){this._trust(e);return}this._confirmTrust=e.id,this._focusInItem(e.id,"[data-trust-cancel]")}}_cancelTrust(e){this._confirmTrust=null,this._focusInItem(e,"[data-trust]")}_onTrustKeyDown(e,r){e.key==="Escape"&&(e.preventDefault(),e.stopPropagation(),this._cancelTrust(r))}async _trust(e){let r=e.sender_domain||e.sender;this._confirmTrust=null,this._trustStatus=null,this._focusInItem(e.id,"[data-trust]"),await this._command(e.id,"review/trust_sender",{review_id:e.id},{hide:!1,onSuccess:i=>{let n=i??{};this._trustStatus=Ji({domain:n.domain??r,added:n.added??0,rechecking:n.rechecking??0,kept:n.kept??0})}})}_dismissTrustStatus(){this._trustStatus=null}async _command(e,r,i,{hide:n=!0,onSuccess:o}={}){let a=this.hass;if(!(!a||this._busyItems.has(e)||this._hidden.has(e))){this._busyItems=new Set([...this._busyItems,e]),this._itemErrors=pr(this._itemErrors,e),n&&(this._hidden=dr(this._hidden,[e]));try{let d=await J(a,r,i);n&&(this._hidden=ur(this._hidden,[e],this.snapshot,c=>this._listed(c))),o?.(d)}catch(d){this._hidden=cr(this._hidden,[e]);let c=m(s.actionFailed,{message:I(d)});this._listed(e)?this._itemErrors=new Map([...this._itemErrors,[e,c]]):this.showActionError(c)}finally{let d=new Set(this._busyItems);d.delete(e),this._busyItems=d}}}};B("parcels-review-card",hr);_e("parcels-review-card",s.reviewCardName,s.reviewCardDescription);
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
