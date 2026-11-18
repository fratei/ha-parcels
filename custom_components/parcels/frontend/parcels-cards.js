var Pe=globalThis,Re=Pe.ShadowRoot&&(Pe.ShadyCSS===void 0||Pe.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,ct=Symbol(),Qt=new WeakMap,ge=class{constructor(e,r,i){if(this._$cssResult$=!0,i!==ct)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=r}get styleSheet(){let e=this.o,r=this.t;if(Re&&e===void 0){let i=r!==void 0&&r.length===1;i&&(e=Qt.get(r)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&Qt.set(r,e))}return e}toString(){return this.cssText}},Zt=t=>new ge(typeof t=="string"?t:t+"",void 0,ct),x=(t,...e)=>{let r=t.length===1?t[0]:e.reduce((i,n,o)=>i+(a=>{if(a._$cssResult$===!0)return a.cssText;if(typeof a=="number")return a;throw Error("Value passed to 'css' function must be a 'css' function result: "+a+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(n)+t[o+1],t[0]);return new ge(r,t,ct)},Jt=(t,e)=>{if(Re)t.adoptedStyleSheets=e.map(r=>r instanceof CSSStyleSheet?r:r.styleSheet);else for(let r of e){let i=document.createElement("style"),n=Pe.litNonce;n!==void 0&&i.setAttribute("nonce",n),i.textContent=r.cssText,t.appendChild(i)}},ut=Re?t=>t:t=>t instanceof CSSStyleSheet?(e=>{let r="";for(let i of e.cssRules)r+=i.cssText;return Zt(r)})(t):t;var{is:yi,defineProperty:$i,getOwnPropertyDescriptor:wi,getOwnPropertyNames:xi,getOwnPropertySymbols:ki,getPrototypeOf:Si}=Object,Me=globalThis,Xt=Me.trustedTypes,Ti=Xt?Xt.emptyScript:"",Ei=Me.reactiveElementPolyfillSupport,_e=(t,e)=>t,pt={toAttribute(t,e){switch(e){case Boolean:t=t?Ti:null;break;case Object:case Array:t=t==null?t:JSON.stringify(t)}return t},fromAttribute(t,e){let r=t;switch(e){case Boolean:r=t!==null;break;case Number:r=t===null?null:Number(t);break;case Object:case Array:try{r=JSON.parse(t)}catch{r=null}}return r}},tr=(t,e)=>!yi(t,e),er={attribute:!0,type:String,converter:pt,reflect:!1,useDefault:!1,hasChanged:tr};Symbol.metadata??=Symbol("metadata"),Me.litPropertyMetadata??=new WeakMap;var B=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,r=er){if(r.state&&(r.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((r=Object.create(r)).wrapped=!0),this.elementProperties.set(e,r),!r.noAccessor){let i=Symbol(),n=this.getPropertyDescriptor(e,i,r);n!==void 0&&$i(this.prototype,e,n)}}static getPropertyDescriptor(e,r,i){let{get:n,set:o}=wi(this.prototype,e)??{get(){return this[r]},set(a){this[r]=a}};return{get:n,set(a){let d=n?.call(this);o?.call(this,a),this.requestUpdate(e,d,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??er}static _$Ei(){if(this.hasOwnProperty(_e("elementProperties")))return;let e=Si(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(_e("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(_e("properties"))){let r=this.properties,i=[...xi(r),...ki(r)];for(let n of i)this.createProperty(n,r[n])}let e=this[Symbol.metadata];if(e!==null){let r=litPropertyMetadata.get(e);if(r!==void 0)for(let[i,n]of r)this.elementProperties.set(i,n)}this._$Eh=new Map;for(let[r,i]of this.elementProperties){let n=this._$Eu(r,i);n!==void 0&&this._$Eh.set(n,r)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let r=[];if(Array.isArray(e)){let i=new Set(e.flat(1/0).reverse());for(let n of i)r.unshift(ut(n))}else e!==void 0&&r.push(ut(e));return r}static _$Eu(e,r){let i=r.attribute;return i===!1?void 0:typeof i=="string"?i:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,r=this.constructor.elementProperties;for(let i of r.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Jt(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,r,i){this._$AK(e,i)}_$ET(e,r){let i=this.constructor.elementProperties.get(e),n=this.constructor._$Eu(e,i);if(n!==void 0&&i.reflect===!0){let o=(i.converter?.toAttribute!==void 0?i.converter:pt).toAttribute(r,i.type);this._$Em=e,o==null?this.removeAttribute(n):this.setAttribute(n,o),this._$Em=null}}_$AK(e,r){let i=this.constructor,n=i._$Eh.get(e);if(n!==void 0&&this._$Em!==n){let o=i.getPropertyOptions(n),a=typeof o.converter=="function"?{fromAttribute:o.converter}:o.converter?.fromAttribute!==void 0?o.converter:pt;this._$Em=n;let d=a.fromAttribute(r,o.type);this[n]=d??this._$Ej?.get(n)??d,this._$Em=null}}requestUpdate(e,r,i,n=!1,o){if(e!==void 0){let a=this.constructor;if(n===!1&&(o=this[e]),i??=a.getPropertyOptions(e),!((i.hasChanged??tr)(o,r)||i.useDefault&&i.reflect&&o===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,i))))return;this.C(e,r,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,r,{useDefault:i,reflect:n,wrapped:o},a){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??r??this[e]),o!==!0||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||i||(r=void 0),this._$AL.set(e,r)),n===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(r){Promise.reject(r)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[n,o]of this._$Ep)this[n]=o;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[n,o]of i){let{wrapped:a}=o,d=this[n];a!==!0||this._$AL.has(n)||d===void 0||this.C(n,void 0,o,d)}}let e=!1,r=this._$AL;try{e=this.shouldUpdate(r),e?(this.willUpdate(r),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(r)):this._$EM()}catch(i){throw e=!1,this._$EM(),i}e&&this._$AE(r)}willUpdate(e){}_$AE(e){this._$EO?.forEach(r=>r.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(r=>this._$ET(r,this[r])),this._$EM()}updated(e){}firstUpdated(e){}};B.elementStyles=[],B.shadowRootOptions={mode:"open"},B[_e("elementProperties")]=new Map,B[_e("finalized")]=new Map,Ei?.({ReactiveElement:B}),(Me.reactiveElementVersions??=[]).push("2.1.2");var mt=globalThis,rr=t=>t,Ie=mt.trustedTypes,ir=Ie?Ie.createPolicy("lit-html",{createHTML:t=>t}):void 0,ft="$lit$",z=`lit$${Math.random().toFixed(9).slice(2)}$`,gt="?"+z,Ai=`<${gt}>`,re=document,ve=()=>re.createComment(""),ye=t=>t===null||typeof t!="object"&&typeof t!="function",_t=Array.isArray,dr=t=>_t(t)||typeof t?.[Symbol.iterator]=="function",ht=`[ 	
\f\r]`,be=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,nr=/-->/g,sr=/>/g,ee=RegExp(`>|${ht}(?:([^\\s"'>=/]+)(${ht}*=${ht}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),or=/'/g,ar=/"/g,cr=/^(?:script|style|textarea|title)$/i,bt=t=>(e,...r)=>({_$litType$:t,strings:e,values:r}),l=bt(1),Wn=bt(2),Kn=bt(3),$=Symbol.for("lit-noChange"),u=Symbol.for("lit-nothing"),lr=new WeakMap,te=re.createTreeWalker(re,129);function ur(t,e){if(!_t(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return ir!==void 0?ir.createHTML(e):e}var pr=(t,e)=>{let r=t.length-1,i=[],n,o=e===2?"<svg>":e===3?"<math>":"",a=be;for(let d=0;d<r;d++){let c=t[d],h,m,p=-1,f=0;for(;f<c.length&&(a.lastIndex=f,m=a.exec(c),m!==null);)f=a.lastIndex,a===be?m[1]==="!--"?a=nr:m[1]!==void 0?a=sr:m[2]!==void 0?(cr.test(m[2])&&(n=RegExp("</"+m[2],"g")),a=ee):m[3]!==void 0&&(a=ee):a===ee?m[0]===">"?(a=n??be,p=-1):m[1]===void 0?p=-2:(p=a.lastIndex-m[2].length,h=m[1],a=m[3]===void 0?ee:m[3]==='"'?ar:or):a===ar||a===or?a=ee:a===nr||a===sr?a=be:(a=ee,n=void 0);let _=a===ee&&t[d+1].startsWith("/>")?" ":"";o+=a===be?c+Ai:p>=0?(i.push(h),c.slice(0,p)+ft+c.slice(p)+z+_):c+z+(p===-2?d:_)}return[ur(t,o+(t[r]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),i]},$e=class t{constructor({strings:e,_$litType$:r},i){let n;this.parts=[];let o=0,a=0,d=e.length-1,c=this.parts,[h,m]=pr(e,r);if(this.el=t.createElement(h,i),te.currentNode=this.el.content,r===2||r===3){let p=this.el.content.firstChild;p.replaceWith(...p.childNodes)}for(;(n=te.nextNode())!==null&&c.length<d;){if(n.nodeType===1){if(n.hasAttributes())for(let p of n.getAttributeNames())if(p.endsWith(ft)){let f=m[a++],_=n.getAttribute(p).split(z),b=/([.?@])?(.*)/.exec(f);c.push({type:1,index:o,name:b[2],strings:_,ctor:b[1]==="."?De:b[1]==="?"?Oe:b[1]==="@"?Ne:ne}),n.removeAttribute(p)}else p.startsWith(z)&&(c.push({type:6,index:o}),n.removeAttribute(p));if(cr.test(n.tagName)){let p=n.textContent.split(z),f=p.length-1;if(f>0){n.textContent=Ie?Ie.emptyScript:"";for(let _=0;_<f;_++)n.append(p[_],ve()),te.nextNode(),c.push({type:2,index:++o});n.append(p[f],ve())}}}else if(n.nodeType===8)if(n.data===gt)c.push({type:2,index:o});else{let p=-1;for(;(p=n.data.indexOf(z,p+1))!==-1;)c.push({type:7,index:o}),p+=z.length-1}o++}}static createElement(e,r){let i=re.createElement("template");return i.innerHTML=e,i}};function ie(t,e,r=t,i){if(e===$)return e;let n=i!==void 0?r._$Co?.[i]:r._$Cl,o=ye(e)?void 0:e._$litDirective$;return n?.constructor!==o&&(n?._$AO?.(!1),o===void 0?n=void 0:(n=new o(t),n._$AT(t,r,i)),i!==void 0?(r._$Co??=[])[i]=n:r._$Cl=n),n!==void 0&&(e=ie(t,n._$AS(t,e.values),n,i)),e}var Le=class{constructor(e,r){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=r}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:r},parts:i}=this._$AD,n=(e?.creationScope??re).importNode(r,!0);te.currentNode=n;let o=te.nextNode(),a=0,d=0,c=i[0];for(;c!==void 0;){if(a===c.index){let h;c.type===2?h=new oe(o,o.nextSibling,this,e):c.type===1?h=new c.ctor(o,c.name,c.strings,this,e):c.type===6&&(h=new He(o,this,e)),this._$AV.push(h),c=i[++d]}a!==c?.index&&(o=te.nextNode(),a++)}return te.currentNode=re,n}p(e){let r=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(e,i,r),r+=i.strings.length-2):i._$AI(e[r])),r++}},oe=class t{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,r,i,n){this.type=2,this._$AH=u,this._$AN=void 0,this._$AA=e,this._$AB=r,this._$AM=i,this.options=n,this._$Cv=n?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,r=this._$AM;return r!==void 0&&e?.nodeType===11&&(e=r.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,r=this){e=ie(this,e,r),ye(e)?e===u||e==null||e===""?(this._$AH!==u&&this._$AR(),this._$AH=u):e!==this._$AH&&e!==$&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):dr(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==u&&ye(this._$AH)?this._$AA.nextSibling.data=e:this.T(re.createTextNode(e)),this._$AH=e}$(e){let{values:r,_$litType$:i}=e,n=typeof i=="number"?this._$AC(e):(i.el===void 0&&(i.el=$e.createElement(ur(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===n)this._$AH.p(r);else{let o=new Le(n,this),a=o.u(this.options);o.p(r),this.T(a),this._$AH=o}}_$AC(e){let r=lr.get(e.strings);return r===void 0&&lr.set(e.strings,r=new $e(e)),r}k(e){_t(this._$AH)||(this._$AH=[],this._$AR());let r=this._$AH,i,n=0;for(let o of e)n===r.length?r.push(i=new t(this.O(ve()),this.O(ve()),this,this.options)):i=r[n],i._$AI(o),n++;n<r.length&&(this._$AR(i&&i._$AB.nextSibling,n),r.length=n)}_$AR(e=this._$AA.nextSibling,r){for(this._$AP?.(!1,!0,r);e!==this._$AB;){let i=rr(e).nextSibling;rr(e).remove(),e=i}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},ne=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,r,i,n,o){this.type=1,this._$AH=u,this._$AN=void 0,this.element=e,this.name=r,this._$AM=n,this.options=o,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=u}_$AI(e,r=this,i,n){let o=this.strings,a=!1;if(o===void 0)e=ie(this,e,r,0),a=!ye(e)||e!==this._$AH&&e!==$,a&&(this._$AH=e);else{let d=e,c,h;for(e=o[0],c=0;c<o.length-1;c++)h=ie(this,d[i+c],r,c),h===$&&(h=this._$AH[c]),a||=!ye(h)||h!==this._$AH[c],h===u?e=u:e!==u&&(e+=(h??"")+o[c+1]),this._$AH[c]=h}a&&!n&&this.j(e)}j(e){e===u?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},De=class extends ne{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===u?void 0:e}},Oe=class extends ne{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==u)}},Ne=class extends ne{constructor(e,r,i,n,o){super(e,r,i,n,o),this.type=5}_$AI(e,r=this){if((e=ie(this,e,r,0)??u)===$)return;let i=this._$AH,n=e===u&&i!==u||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,o=e!==u&&(i===u||n);n&&this.element.removeEventListener(this.name,this,i),o&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},He=class{constructor(e,r,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=r,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){ie(this,e)}},hr={M:ft,P:z,A:gt,C:1,L:pr,R:Le,D:dr,V:ie,I:oe,H:ne,N:Oe,U:Ne,B:De,F:He},Ci=mt.litHtmlPolyfillSupport;Ci?.($e,oe),(mt.litHtmlVersions??=[]).push("3.3.3");var mr=(t,e,r)=>{let i=r?.renderBefore??e,n=i._$litPart$;if(n===void 0){let o=r?.renderBefore??null;i._$litPart$=n=new oe(e.insertBefore(ve(),o),o,void 0,r??{})}return n._$AI(t),n};var vt=globalThis,P=class extends B{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let r=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=mr(r,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return $}};P._$litElement$=!0,P.finalized=!0,vt.litElementHydrateSupport?.({LitElement:P});var Pi=vt.litElementPolyfillSupport;Pi?.({LitElement:P});(vt.litElementVersions??=[]).push("4.2.2");var k={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},q=t=>(...e)=>({_$litDirective$:t,values:e}),R=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,r,i){this._$Ct=e,this._$AM=r,this._$Ci=i}_$AS(e,r){return this.update(e,r)}update(e,r){return this.render(...r)}};var{I:Ri}=hr,fr=t=>t;var _r=t=>t.strings===void 0,gr=()=>document.createComment(""),ae=(t,e,r)=>{let i=t._$AA.parentNode,n=e===void 0?t._$AB:e._$AA;if(r===void 0){let o=i.insertBefore(gr(),n),a=i.insertBefore(gr(),n);r=new Ri(o,a,t,t.options)}else{let o=r._$AB.nextSibling,a=r._$AM,d=a!==t;if(d){let c;r._$AQ?.(t),r._$AM=t,r._$AP!==void 0&&(c=t._$AU)!==a._$AU&&r._$AP(c)}if(o!==n||d){let c=r._$AA;for(;c!==o;){let h=fr(c).nextSibling;fr(i).insertBefore(c,n),c=h}}}return r},V=(t,e,r=t)=>(t._$AI(e,r),t),Mi={},Fe=(t,e=Mi)=>t._$AH=e,br=t=>t._$AH,Ue=t=>{t._$AR(),t._$AA.remove()};var vr=(t,e,r)=>{let i=new Map;for(let n=e;n<=r;n++)i.set(t[n],n);return i},j=q(class extends R{constructor(t){if(super(t),t.type!==k.CHILD)throw Error("repeat() can only be used in text expressions")}dt(t,e,r){let i;r===void 0?r=e:e!==void 0&&(i=e);let n=[],o=[],a=0;for(let d of t)n[a]=i?i(d,a):a,o[a]=r(d,a),a++;return{values:o,keys:n}}render(t,e,r){return this.dt(t,e,r).values}update(t,[e,r,i]){let n=br(t),{values:o,keys:a}=this.dt(e,r,i);if(!Array.isArray(n))return this.ut=a,o;let d=this.ut??=[],c=[],h,m,p=0,f=n.length-1,_=0,b=o.length-1;for(;p<=f&&_<=b;)if(n[p]===null)p++;else if(n[f]===null)f--;else if(d[p]===a[_])c[_]=V(n[p],o[_]),p++,_++;else if(d[f]===a[b])c[b]=V(n[f],o[b]),f--,b--;else if(d[p]===a[b])c[b]=V(n[p],o[b]),ae(t,c[b+1],n[p]),p++,b--;else if(d[f]===a[_])c[_]=V(n[f],o[_]),ae(t,n[p],n[f]),f--,_++;else if(h===void 0&&(h=vr(a,_,b),m=vr(d,p,f)),h.has(d[p]))if(h.has(d[f])){let T=m.get(a[_]),dt=T!==void 0?n[T]:null;if(dt===null){let Gt=ae(t,n[p]);V(Gt,o[_]),c[_]=Gt}else c[_]=V(dt,o[_]),ae(t,n[p],dt),n[T]=null;_++}else Ue(n[f]),f--;else Ue(n[p]),p++;for(;_<=b;){let T=ae(t,c[b+1]);V(T,o[_]),c[_++]=T}for(;p<=f;){let T=n[p++];T!==null&&Ue(T)}return this.ut=a,Fe(t,c),$}});var yr="important",Ii=" !"+yr,M=q(class extends R{constructor(t){if(super(t),t.type!==k.ATTRIBUTE||t.name!=="style"||t.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(t){return Object.keys(t).reduce((e,r)=>{let i=t[r];return i==null?e:e+`${r=r.includes("-")?r:r.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${i};`},"")}update(t,[e]){let{style:r}=t.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(e)),this.render(e);for(let i of this.ft)e[i]==null&&(this.ft.delete(i),i.includes("-")?r.removeProperty(i):r[i]=null);for(let i in e){let n=e[i];if(n!=null){this.ft.add(i);let o=typeof n=="string"&&n.endsWith(Ii);i.includes("-")||o?r.setProperty(i,o?n.slice(0,-11):n,o?yr:""):r[i]=n}}return $}});var E=q(class extends R{constructor(t){if(super(t),t.type!==k.PROPERTY&&t.type!==k.ATTRIBUTE&&t.type!==k.BOOLEAN_ATTRIBUTE)throw Error("The `live` directive is not allowed on child or event bindings");if(!_r(t))throw Error("`live` bindings can only contain a single expression")}render(t){return t}update(t,[e]){if(e===$||e===u)return e;let r=t.element,i=t.name;if(t.type===k.PROPERTY){if(e===r[i])return $}else if(t.type===k.BOOLEAN_ATTRIBUTE){if(!!e===r.hasAttribute(i))return $}else if(t.type===k.ATTRIBUTE&&r.getAttribute(i)===e+"")return $;return Fe(t),e}});var $r="parcels";function Y(t,e,r){return t.callService($r,e,r,void 0,!1)}function we(t,e,r={}){return t.callWS({...r,type:`${$r}/${e}`})}var G={amazon:"Amazon Logistics",asendia:"Asendia",bpost:"bpost",brt:"BRT",cainiao:"Cainiao",chronopost:"Chronopost",colissimo:"Colissimo",correos:"Correos",correos_express:"Correos Express",ctt:"CTT",ctt_expresso:"CTT Expresso",deutsche_post:"Deutsche Post",dhl:"DHL",dpd:"DPD",evri:"Evri",fedex:"FedEx",gls:"GLS",hermes:"Hermes",inpost:"InPost",la_poste:"La Poste",mondial_relay:"Mondial Relay",mrw:"MRW",nacex:"Nacex",paack:"Paack",postnl:"PostNL",poste_italiane:"Poste Italiane",royal_mail:"Royal Mail",sda:"SDA",seur:"SEUR",tnt:"TNT",ups:"UPS",usps:"USPS",vinted_go:"Vinted Go",yunexpress:"YunExpress",other:"Other"};function Be(){return Object.entries(G).filter(([t])=>t!=="other").map(([t,e])=>({id:t,name:e})).sort((t,e)=>t.name.localeCompare(e.name,"en",{sensitivity:"base"})).concat([{id:"other",name:G.other??"Other"}])}function wr(t){return Object.hasOwn(G,t)?G[t]??t:t}var s={weekCardName:"Parcels week",weekCardDescription:"A Monday to Sunday calendar of your parcel deliveries.",listCardName:"Parcels without a date",listCardDescription:"Active parcels that don't have a delivery date yet.",reviewCardName:"Parcels review",reviewCardDescription:"E-mails that need a decision before Parcels uses them. Only shown to administrators.",defaultWeekTitle:"Parcels",defaultListTitle:"No date yet",defaultReviewTitle:"Parcels review",loading:"Loading parcels\u2026",loadError:"Couldn't load parcels: {message}",refreshError:"Couldn't update parcels: {message}",unknownError:"Unknown error",close:"Close",cancel:"Cancel",save:"Save",dismissMessage:"Dismiss message",configInvalid:"Invalid configuration: expected a map of options.",configTitle:'Invalid configuration: "title" must be text.',configShowArchived:'Invalid configuration: "show_archived" must be true or false.',previousWeek:"Previous week",nextWeek:"Next week",today:"Today",goToToday:"Go to the current week",weekNavigation:"Week navigation",weekOf:"Week of {range}",refresh:"Check mailboxes now",refreshFailed:"Couldn't check the mailboxes: {message}",addParcel:"Add parcel",noDeliveriesThisWeek:"No deliveries this week",noDeliveriesThisDay:"No deliveries",todayTag:"Today",privateParcel:"Private parcel",unnamedParcel:"Parcel",packages:"{count} packages",carrierNotKnown:"Carrier not known yet",carrierNotKnownLabel:"carrier not known yet",carrierIs:"carrier {carrier}",hasCode:"PIN in the details",aiBadge:"AI",aiBadgeLabel:"found by the local AI",privateLabel:"private",autoMerged:"Auto-merged \u2014 check",autoMergedLabel:"merged automatically, please check",undo:"Undo",undoMergeLabel:"Undo the automatic merge of {title}",undoFailed:"Couldn't undo the merge: {message}",keep:"Keep",keepMergeLabel:"Keep the automatic merge of {title}",keepFailed:"Couldn't keep the merge: {message}",inferred:"Delivery inferred \u2014 check",inferredLabel:"delivery inferred, please check",undoInferredLabel:"Undo the inferred delivery of {title}",undoInferredFailed:"Couldn't undo the delivery: {message}",keepInferredLabel:"Keep the inferred delivery of {title}",keepInferredFailed:"Couldn't keep the delivery: {message}",continuesBefore:"started before this week",continuesAfter:"continues after this week",deliveredOn:"delivered {date}",returnedOn:"returned {date}",expectedOn:"expected {date}",readyForPickupSince:"ready for pickup since {date}",statusOn:"{status} on {date}",windowFrom:"from {time}",windowUntil:"until {time}",noUndatedParcels:"Every active parcel has a delivery date.",tabReview:"Needs review",tabFiltered:"Filtered",tabCount:"{label} ({count})",possibleDuplicate:"Possible duplicate",suggestionTitle:"Same parcel as {parcel}?",suggestionHint:"Merge the parcel that is the same one, or keep them apart.",reasonIs:"Reason: {reason}",mergeSuggested:"Merge",mergeSuggestedLabel:"Merge {candidate} into {title}",keepApart:"Keep apart",keepApartLabel:"Keep {title} apart from these parcels",reviewTabs:"Review lists",emptyReview:"Nothing to review.",emptyFiltered:"No filtered e-mails.",filteredHint:"E-mails the local AI classed as not about a parcel.",receivedOn:"Received {date}",noSubject:"(no subject)",mailboxOf:"Mailbox: {owner}",unverifiedSender:"Unverified sender",unverifiedSenderHint:"This e-mail didn't pass the sender checks (DKIM/DMARC). Make sure it's genuine before you accept it.",aiSuggestionLabel:"read by the local AI",suggestion:"Suggestion",noSuggestion:"No suggestion. Use Edit to enter the details yourself.",accept:"Accept",acceptWithChanges:"Accept with changes",edit:"Edit",dismiss:"Dismiss",trustSender:"Trust this sender",trustSenderHint:"Treat e-mails from {domain} as a known sender from now on",ignoreSender:"Ignore this sender",ignoreSenderHint:"Skip e-mails from {domain} from now on",restore:"Restore",clear:"Clear",clearHint:"Remove this e-mail from the list. It won't be read again.",clearAll:"Clear all",clearAllQuestion:"Clear all filtered e-mails? They won't be read again.",aiQueueOne:"1 e-mail waiting for the local AI",aiQueueMany:"{count} e-mails waiting for the local AI",aiQueueMinutes:"{queue}, about {minutes} min",aiQueueHours:"{queue}, about {hours} h",fieldKind:"Type",fieldMerchant:"Merchant",fieldCarrier:"Carrier",fieldTrackingNumber:"Tracking number",fieldTrackingNumbers:"Tracking numbers",fieldOrderNumbers:"Order numbers",fieldEtaStart:"Expected from",fieldEtaEnd:"Expected until",fieldWindowStart:"Time window from",fieldWindowEnd:"Time window until",fieldPickupPoint:"Pickup point",fieldPickupCode:"PIN or pickup code",fieldItems:"Items",fieldPrivate:"Private (only the owners can see it)",hintList:"Separate with commas or new lines.",hintItems:"One per line.",carrierAuto:"Detect automatically",carrierUnknown:"Unknown",details:"Parcel details",status:"Status",sinceDate:"since {date}",carrier:"Delivered by",notKnownYet:"Not known yet",trackOnline:"Track on the carrier's site",opensInNewTab:"(opens in a new tab)",trackingNumber:"Tracking number",copy:"Copy",copyTrackingNumber:"Copy the tracking number",copied:"Copied.",copyFailed:"Couldn't copy automatically. The number is selected, so you can copy it yourself.",merchant:"Merchant",orders:"Orders",items:"Items",expected:"Expected",timeWindow:"Time window",pickupPoint:"Pickup point",pickupCode:"PIN or pickup code",packagesInShipment:"Packages",showPackage:"Show package {name}",parcelId:"Parcel ID",delivered:"Delivered",timeline:"Timeline",noTimeline:"No events yet.",provisional:"Provisional",provisionalHint:"Made from an order e-mail. It's completed when the shipping e-mail arrives.",archived:"Archived",private:"Private",loadingDetails:"Loading details\u2026",detailsError:"Couldn't load the details: {message}",retry:"Try again",notFound:"This parcel no longer exists.",aiNotice:"Found by the local AI. Check the details, then confirm them.",confirm:"Confirm",confirmLabel:"Confirm the details the local AI found",mergedNotice:"Merged automatically ({reason}). Check that it's one parcel.",mergedNoticeNoReason:"Merged automatically. Check that it's one parcel.",inferredNotice:"Probably delivered: another parcel from this shop was delivered around the expected day. Undo if it hasn't arrived.",markDelivered:"Mark delivered",editDate:"Edit date",mergeWith:"Merge with\u2026",split:"Split\u2026",archive:"Archive",actions:"Actions",mergeIntro:"Choose the parcel to merge into this one.",mergeChoose:"Parcel",mergeConfirm:"Merge",noMergeCandidates:"There are no other active parcels to merge with.",splitIntro:"Choose what to move to a new parcel.",splitConfirm:"Split off",splitHint:"Choose at least one, but not all of them.",archiveQuestion:"Archive this parcel? It no longer counts as active.",dateEndBeforeStart:"The end date is before the start date.",dateEndWithoutStart:"Set a start date too.",windowEndBeforeStart:"The time window must end after it starts.",actionFailed:"That didn't work: {message}",addTitle:"Add parcel",addSubmit:"Add",trackingRequired:"Enter a tracking number."},xr={ordered:"Ordered",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",exception:"Problem with delivery",ready_for_pickup:"Ready for pickup",returned:"Returned",cancelled:"Cancelled"},ze={order:"Order confirmation",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",ready_for_pickup:"Ready for pickup",delayed:"Delayed",customs:"Held at customs",return:"Return",cancelled:"Cancelled",code:"Delivery code",not_parcel:"Not about a parcel",unknown:"Unknown"},kr={parser:"E-mail",ai:"Local AI",manual:"Added by hand",seventeentrack:"17TRACK",inferred:"Inferred from another delivery"},Sr={unknown_sender:"Unknown sender",not_aligned:"The sender's domain isn't authenticated (DKIM/DMARC)",no_auth_header:"No authentication results in the e-mail",untrusted_authserv:"Authentication results from an unknown server",low_confidence:"Not sure about the details",unknown_format:"Unknown e-mail format",ai_suggestion:"Read by the local AI",ai_unavailable:"The local AI wasn't available",ai_rejected:"The local AI's answer didn't pass the checks",restored:"Moved back from Filtered"},Tr={same_number:"same tracking number",same_merchant_eta:"same shop and delivery date",same_merchant_day:"same shop, delivered on the expected day",same_merchant_domain:"the shop's tracked shipment followed its order",same_order:"same order"};function g(t,e){return t.replace(/\{(\w+)\}/g,(r,i)=>Object.hasOwn(e,i)?String(e[i]):r)}function A(t){if(typeof t=="string"&&t.trim())return t;if(t&&typeof t=="object"){let e=t.message;if(typeof e=="string"&&e.trim())return e;let r=t.code;if(typeof r=="string"&&r.trim())return r}return s.unknownError}var Li=["a[href]","button:not([disabled])","input:not([disabled]):not([type='hidden'])","select:not([disabled])","textarea:not([disabled])","[tabindex]:not([tabindex='-1'])"].join(",");function Di(t){return[...t.querySelectorAll(Li)].filter(e=>!e.closest("[hidden], [inert]")&&e.getClientRects().length>0)}function Er(t,e){if(t.key!=="Tab"||t.altKey||t.ctrlKey||t.metaKey)return;let r=Di(e),i=r[0],n=r[r.length-1];if(!i||!n){t.preventDefault(),e.focus();return}let a=e.getRootNode().activeElement,d=a instanceof HTMLElement&&e.contains(a)&&a!==e;t.shiftKey&&(!d||a===i)?(t.preventDefault(),n.focus()):!t.shiftKey&&(!d||a===n)&&(t.preventDefault(),i.focus())}var Oi="parcels-error",le=class extends P{static properties={hass:{attribute:!1},_open:{state:!0},_busy:{state:!0},_error:{state:!0}};_returnFocus=null;_pressedBackdrop=!1;_hadFocus=!1;_session=0;constructor(){super(),this.hass=void 0,this._open=!1,this._busy=!1,this._error=null}render(){return l`<dialog
      aria-labelledby="dialog-title"
      @close=${this._onClose}
      @keydown=${this._onKeyDown}
      @pointerdown=${this._onPointerDown}
      @click=${this._onClick}
    >
      ${this._open?this.renderContent():u}
    </dialog>`}renderContent(){return u}canLightDismiss(){return!this._busy}dialogClosed(){}get isOpen(){return this._open}async showDialog(e){this._session+=1,this._returnFocus=e,this._open=!0,this._busy=!1,this._error=null,await this.updateComplete;let r=this._dialog();!r||!this._open||!this.isConnected||(r.open||r.showModal(),this.focusInDialog("[data-autofocus]"))}closeDialog(){let e=this._dialog();e?.open&&e.close(),this._finishClose(!0)}focusInDialog(e){this.renderRoot.querySelector(`dialog ${e}`)?.focus()}async focusAfterRender(e){await this.updateComplete,this._open&&this.focusInDialog(e)}async runAction(e,r){if(this._busy)return;let i=this._session;this._busy=!0,this._error=null;try{await e(),this._open&&this._session===i&&r?.()}catch(n){let o=g(s.actionFailed,{message:A(n)});this._open&&this._session===i?this._error=o:this.dispatchEvent(new CustomEvent(Oi,{detail:o}))}finally{this._session===i&&(this._busy=!1)}}disconnectedCallback(){super.disconnectedCallback(),this._finishClose(!1)}willUpdate(e){this._hadFocus=this._open&&!!this.shadowRoot?.activeElement}updated(e){this._hadFocus&&this._open&&!this.shadowRoot?.activeElement&&this.focusInDialog("[data-autofocus]"),this._hadFocus=!1}_dialog(){return this.renderRoot.querySelector("dialog")}_finishClose(e){if(!this._open)return;let r=this._returnFocus;this._returnFocus=null,this._open=!1,this._busy=!1,this._error=null,this._pressedBackdrop=!1,this.dialogClosed(),e&&r?.()}_onClose(e){let r=e.currentTarget;e.target===r&&!r.open&&this._finishClose(!0)}_onKeyDown(e){Er(e,e.currentTarget)}_onPointerDown(e){this._pressedBackdrop=e.target===e.currentTarget}_onClick(e){let r=this._pressedBackdrop&&e.target===e.currentTarget;this._pressedBackdrop=!1,r&&this.canLightDismiss()&&this.closeDialog()}};var Ni=/^(\d{4})-(\d{2})-(\d{2})$/,Hi=/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)(?:[.,](\d+))?(Z|[+-]\d{2}(?::?\d{2})?)?$/i,Fi=[31,28,31,30,31,30,31,31,30,31,30,31];function Ui(t){return t%4===0&&t%100!==0||t%400===0}function Bi(t,e){return e===2&&Ui(t)?29:Fi[e-1]??0}function Ke(t){if(typeof t!="string")return null;let e=Ni.exec(t);if(!e)return null;let r=Number(e[1]),i=Number(e[2]),n=Number(e[3]);return i<1||i>12||n<1||n>Bi(r,i)?null:{year:r,month:i,day:n}}function W(t){return Ke(t)!==null}function je(t){let e=Ke(t);if(!e)throw new RangeError(`Not a YYYY-MM-DD date: ${t}`);return e}function We({year:t,month:e,day:r}){let i=e<=2?t-1:t,n=Math.floor(i/400),o=i-n*400,a=(e+9)%12,d=Math.floor((153*a+2)/5)+r-1,c=o*365+Math.floor(o/4)-Math.floor(o/100)+d;return n*146097+c-719468}function zi(t){let e=t+719468,r=Math.floor(e/146097),i=e-r*146097,n=Math.floor((i-Math.floor(i/1460)+Math.floor(i/36524)-Math.floor(i/146096))/365),o=i-(365*n+Math.floor(n/4)-Math.floor(n/100)),a=Math.floor((5*o+2)/153),d=o-Math.floor((153*a+2)/5)+1,c=a<10?a+3:a-9;return{year:n+r*400+(c<=2?1:0),month:c,day:d}}function ji({year:t,month:e,day:r}){return`${String(t).padStart(4,"0")}-${String(e).padStart(2,"0")}-${String(r).padStart(2,"0")}`}function de(t,e){return ji(zi(We(je(t))+e))}function yt(t,e){return We(je(e))-We(je(t))}function Wi(t){return((We(je(t))+3)%7+7)%7}function Cr(t){return de(t,-Wi(t))}function Pr(t){return Array.from({length:7},(e,r)=>de(t,r))}function I(t,e){return t<e?-1:t>e?1:0}function Rr(t,e){return I(t,e)>=0?t:e}function L(t){if(typeof t!="string")return null;let e=Hi.exec(t.trim());if(!e)return null;let[,r,i,n,o]=e;if(!r||!i||!W(r))return null;let a=n?`.${n.slice(0,3).padEnd(3,"0")}`:"",d="Z";if(o&&o.toUpperCase()!=="Z"){let h=o.slice(1).replace(":","").padEnd(4,"0");d=`${o[0]}${h.slice(0,2)}:${h.slice(2,4)}`}let c=Date.parse(`${r}T${i}${a}${d}`);return Number.isNaN(c)?null:c}var Ar=new Map;function Ki(t){let e=Ar.get(t);if(!e){let r={calendar:"gregory",numberingSystem:"latn",year:"numeric",month:"2-digit",day:"2-digit"};try{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:t})}catch{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:"UTC"})}Ar.set(t,e)}return e}function xe(t,e){if(W(t))return t;let r=L(t);if(r===null)return null;let i="",n="",o="";for(let d of Ki(e).formatToParts(r))d.type==="year"?i=d.value:d.type==="month"?n=d.value:d.type==="day"&&(o=d.value);let a=`${i.padStart(4,"0")}-${n}-${o}`;return W(a)?a:null}function qi(t){return[...new Set(t)]}function Mr(t){return qi(t.split(/[\n,;]+/).map(e=>e.trim()).filter(Boolean))}function Vi(t){return t.split(/\r?\n/).map(e=>e.trim()).filter(Boolean)}function O(t){let e=/^(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?$/.exec((t??"").trim());if(!e)return null;let r=Number(e[1]),i=Number(e[2]);return r>23||i>59?null:`${String(r).padStart(2,"0")}:${String(i).padStart(2,"0")}`}function D(t){let e=t.trim();return e||null}function Yi(t,e){return e&&!t?s.dateEndWithoutStart:t&&e&&I(e,t)<0?s.dateEndBeforeStart:null}function Gi(t,e){let r=O(t),i=O(e);return r&&i&&i<=r?s.windowEndBeforeStart:null}function Ir(t){return{eta_start:t.eta_start??"",eta_end:t.eta_end??"",window_start:O(t.window_start)??"",window_end:O(t.window_end)??""}}function qe(t){let e=Yi(t.eta_start,t.eta_end);if(e)return{message:e,field:e===s.dateEndWithoutStart?"eta_start":"eta_end"};let r=Gi(t.window_start,t.window_end);return r?{message:r,field:"window_end"}:null}function Lr(t,e){return{parcel_id:t,eta_start:D(e.eta_start),eta_end:D(e.eta_end),window_start:O(e.window_start),window_end:O(e.window_end)}}var Dr="shipped";function $t(t){return{kind:t?.kind||Dr,merchant:t?.merchant??"",carrier:t?.carrier??"",tracking_numbers:(t?.tracking_numbers??[]).join(", "),order_numbers:(t?.order_numbers??[]).join(", "),eta_start:t?.eta_start??"",eta_end:t?.eta_end??"",window_start:O(t?.window_start)??"",window_end:O(t?.window_end)??"",pickup_point:t?.pickup_point??"",pickup_code:t?.pickup_code??"",items:(t?.items??[]).join(`
`)}}function Or(t){return{kind:t.kind.trim()||Dr,merchant:D(t.merchant),carrier:D(t.carrier),tracking_numbers:Mr(t.tracking_numbers),order_numbers:Mr(t.order_numbers),eta_start:D(t.eta_start),eta_end:D(t.eta_end),window_start:O(t.window_start),window_end:O(t.window_end),pickup_point:D(t.pickup_point),pickup_code:D(t.pickup_code),items:Vi(t.items)}}function Nr(t){let e=t.tracking_number.trim();if(!e)return null;let r={tracking_number:e},i=D(t.carrier);i&&(r.carrier=i);let n=D(t.merchant);return n&&(r.merchant=n),t.private&&(r.private=!0),r}function wt(t,e){return t.length>0&&t.length<e}var Qi="https://github.com/fratei/ha-parcels";function N(t,e){customElements.get(t)||customElements.define(t,e)}function ce(t,e,r){let i=window;Array.isArray(i.customCards)||(i.customCards=[]);let n=i.customCards;n.some(o=>o?.type===t)||n.push({type:t,name:e,description:r,preview:!0,documentationURL:Qi})}var H=x`
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
`,Ve=x`
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
  .merge-note .merge-detail {
    color: var(--secondary-text-color, #727272);
    font-weight: 400;
    overflow-wrap: anywhere;
  }
`,Ye=x`
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
`;var Hr={tracking_number:"",carrier:"",merchant:"",private:!1},xt=class extends le{static properties={_form:{state:!0},_missingNumber:{state:!0}};static styles=[H,Ye,x`
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
    `];constructor(){super(),this._form=Hr,this._missingNumber=!1}async open(e=null){this._form=Hr,this._missingNumber=!1,await this.showDialog(e)}canLightDismiss(){return!1}renderContent(){let e=this._form,r=this._missingNumber;return l`
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
              .value=${E(e.tracking_number)}
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
              ${Be().map(i=>l`<option value=${i.id} ?selected=${e.carrier===i.id}>
                    ${i.name}
                  </option>`)}
            </select>
          </label>
          <label class="field">
            <span class="field-label">${s.fieldMerchant}</span>
            <input
              name="merchant"
              autocomplete="off"
              .value=${E(e.merchant)}
              @input=${this._onInput}
            />
          </label>
          <label class="check-row">
            <input
              type="checkbox"
              name="private"
              .checked=${E(e.private)}
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
    `}_onInput(e){let r=e.currentTarget,i=r.name,n=r instanceof HTMLInputElement&&r.type==="checkbox"?r.checked:r.value;this._form={...this._form,[i]:n},i==="tracking_number"&&this._missingNumber&&r.value.trim()&&(this._missingNumber=!1)}_submit(e){e.preventDefault();let r=this.hass;if(!r||this._busy)return;let i=Nr(this._form);if(!i){this._missingNumber=!0,this.focusAfterRender("#tracking-number");return}this.runAction(()=>Y(r,"add",i),()=>this.closeDialog())}};N("parcels-add-dialog",xt);var kt=q(class extends R{constructor(t){if(super(t),t.type!==k.ATTRIBUTE||t.name!=="class"||t.strings?.length>2)throw Error("`classMap()` can only be used in the `class` attribute and must be the only part in the attribute.")}render(t){return" "+Object.keys(t).filter(e=>t[e]).join(" ")+" "}update(t,[e]){if(this.st===void 0){this.st=new Set,t.strings!==void 0&&(this.nt=new Set(t.strings.join(" ").split(/\s/).filter(i=>i!=="")));for(let i in e)e[i]&&!this.nt?.has(i)&&this.st.add(i);return this.render(e)}let r=t.element.classList;for(let i of this.st)i in e||(r.remove(i),this.st.delete(i));for(let i in e){let n=!!e[i];n===this.st.has(i)||this.nt?.has(i)||(n?(r.add(i),this.st.add(i)):(r.remove(i),this.st.delete(i)))}return $}});function Zi(t){try{return Intl.DateTimeFormat.supportedLocalesOf([t]),t}catch{return"en"}}function Ji(){let t=new Intl.DateTimeFormat(void 0,{hour:"numeric"}).resolvedOptions().hourCycle;return t==="h11"||t==="h12"}function Qe(t,e){let r=Zi(t?.locale?.language||t?.language||"en"),i=t?.locale?.time_format,n;i==="12"?n=!0:i==="24"?n=!1:i==="system"&&(n=Ji());let o=t?.locale?.time_zone==="local"?void 0:e||t?.config?.time_zone||void 0;return{language:r,hour12:n,timeZone:o}}var Fr=new Map;function ke(t,e,r){let i=e.hour!==void 0||e.timeStyle!==void 0,n={...e,timeZone:r?"UTC":t.timeZone};i&&t.hour12!==void 0&&(n.hour12=t.hour12);let o=JSON.stringify([t.language,n]),a=Fr.get(o);if(!a){try{a=new Intl.DateTimeFormat(t.language,n)}catch{a=new Intl.DateTimeFormat(t.language,{...n,timeZone:void 0})}Fr.set(o,a)}return a}function St(t){let e=Ke(t);return e?new Date(Date.UTC(e.year,e.month-1,e.day)):null}var Ur={weekday:"short",day:"numeric",month:"short"},Br={day:"numeric",month:"short",year:"numeric"};function se(t,e,r=Ur){let i=St(t);return i?ke(e,r,!0).format(i):t}function C(t,e,r,i=Ur){let n=St(t),o=St(e);return!n||!o?[t,e].filter(Boolean).join(" \u2013 "):t===e?ke(r,i,!0).format(n):ke(r,i,!0).formatRange(n,o)}function Ge(t,e){let r=/^(\d{1,2}):(\d{2})/.exec(t);if(!r)return t;let i=new Date(Date.UTC(1970,0,1,Number(r[1]),Number(r[2])));return ke(e,{hour:"numeric",minute:"2-digit"},!0).format(i)}function ue(t,e,r){return t&&e?`${Ge(t,r)}\u2013${Ge(e,r)}`:t?g(s.windowFrom,{time:Ge(t,r)}):e?g(s.windowUntil,{time:Ge(e,r)}):null}function F(t,e){if(!t)return"";let r=L(t);return r===null?t:ke(e,{dateStyle:"medium",timeStyle:"short"},!1).format(r)}function Se(t){if(typeof t!="string")return null;let e=t.trim();return e||null}function zr(t){let e=t.trim();if(!/^[a-z0-9]+(?:[_-][a-z0-9]+)*$/.test(e))return e;let r=e.replace(/[_-]+/g," ");return r.charAt(0).toUpperCase()+r.slice(1)}function Te(t,e){let r=Se(e);return r?Object.hasOwn(t,r)?t[r]??r:zr(r):""}function Q(t){let e=Se(t.carrier_name);if(e)return e;let r=Se(t.carrier);return!r||r==="other"?null:Object.hasOwn(G,r)?wr(r):zr(r)}function w(t){return t.restricted?s.privateParcel:Se(t.merchant)??Q(t)??Se(t.tracking_number)??s.unnamedParcel}function Ze(t){let e=Q(t);return e&&e!==w(t)?e:null}function K(t){return Te(xr,t)}function Tt(t){return Te(ze,t)}function Et(t){return Te(kr,t)}function jr(t){return Te(Sr,t)}function Je(t){return Te(Tr,t)}var Xe="var(--secondary-text-color, #727272)",Wr="var(--info-color, #039be5)",Xi="var(--warning-color, #ffa600)",en="var(--success-color, #43a047)",Kr="var(--error-color, #db4437)",tn="var(--purple-color, #926bc7)",qr={ordered:Xe,shipped:Wr,in_transit:Wr,out_for_delivery:Xi,delivered:en,attempted:Kr,exception:Kr,ready_for_pickup:tn,returned:Xe,cancelled:Xe};function Ee(t){return Object.hasOwn(qr,t)?qr[t]:Xe}var rn=new Set(["delivered","returned","cancelled"]);function et(t){return!rn.has(t)}function U(t){let e=W(t.eta_start)?t.eta_start:null,r=W(t.eta_end)?t.eta_end:null,i=e??r;return i?{start:i,end:r&&I(r,i)>=0?r:i}:null}function Vr(t){return et(t.status)}function Yr(t,e){let r=L(t.status_time),i=L(e.status_time);return r!==i?r===null?1:i===null?-1:i-r:t.id<e.id?-1:t.id>e.id?1:0}function Gr(t){return t.filter(e=>Vr(e)&&!e.archived&&U(e)===null).sort(Yr)}function tt(t,e){return t.filter(r=>r.id!==e&&Vr(r)&&!r.archived&&!r.restricted).sort(Yr)}function Qr(t,e,r){return e?.kind==="delivered"||e?.kind==="returned"?null:ue(t.window_start,t.window_end,r)}function Zr(t){return!t.restricted&&Q(t)===null}function Jr(t){return t!==void 0&&t>1?g(s.packages,{count:String(t)}):null}function Xr(t,e){let r=e.placement??null,i=[];if(e.showStatus){let d=K(t.status);d&&i.push(d)}let n=Jr(e.count);n&&i.push(n);let o=Ze(t);o&&i.push(o),e.showRange&&r&&r.from!==r.to&&i.push(C(r.from,r.to,e.locale));let a=Qr(t,r,e.locale);return a&&i.push(a),Zr(t)&&i.push(s.carrierNotKnown),i.join(" \xB7 ")}function ei(t,e){let{locale:r}=e,i=e.placement??null,n=[w(t)],o=Jr(e.count);o&&n.push(o);let a=Ze(t);a?n.push(g(s.carrierIs,{carrier:a})):Zr(t)&&n.push(s.carrierNotKnownLabel);let d=K(t.status),c=i?se(i.from,r):"";switch(i?.kind){case"delivered":n.push(g(s.deliveredOn,{date:c}));break;case"returned":n.push(g(s.returnedOn,{date:c}));break;case"pickup":n.push(g(s.readyForPickupSince,{date:c}));break;case"status":n.push(g(s.statusOn,{status:d,date:c}));break;case"eta":d&&n.push(d),n.push(g(s.expectedOn,{date:C(i.from,i.to,r)}));break;default:d&&n.push(d);break}let h=Qr(t,i,r);return h&&n.push(h),t.restricted||(t.ai&&n.push(s.aiBadgeLabel),t.auto_merged&&n.push(s.autoMergedLabel),t.inferred&&n.push(s.inferredLabel),t.has_code&&n.push(s.hasCode)),(t.private||t.restricted)&&n.push(s.privateLabel),e.continuesBefore&&n.push(s.continuesBefore),e.continuesAfter&&n.push(s.continuesAfter),n.join(", ")}function Ae(t,e){let r=[w(t)],i=Ze(t);i&&r.push(i);let n=t.tracking_number?.trim();n&&n!==r[0]&&r.push(n);let o=U(t);return r.push(o?C(o.start,o.end,e):K(t.status)),r.filter(Boolean).join(" \xB7 ")}function At(t,e){let r=[],i=new Map;for(let n of t){let o=e(n),a=o===null?void 0:i.get(o);if(a){a.push(n);continue}let d=[n];r.push(d),o!==null&&i.set(o,d)}return r}function Ct(t,...e){return t.restricted||t.shipment_group===null?null:JSON.stringify([t.shipment_group,t.status,...e])}function pe(t,e){return t.id<e.id?-1:t.id>e.id?1:0}function ti(t){return At(t,e=>Ct(e)).map(e=>{let r=[...e].sort(pe);return{parcel:e.reduce((i,n)=>pe(n,i)<0?n:i),members:r}})}function nn(t){return t.reduce((e,r)=>r!==null&&(e===null||r<e)?r:e,null)}function sn(t){return t.reduce((e,r)=>r!==null&&(e===null||r>e)?r:e,null)}function ri(t,e){return e.length<2?t:{...t,window_start:nn(e.map(r=>r.window_start)),window_end:sn(e.map(r=>r.window_end)),ai:e.some(r=>r.ai),private:e.some(r=>r.private),has_code:e.some(r=>r.has_code),auto_merged:e.find(r=>r.auto_merged)?.auto_merged??null,inferred:e.some(r=>r.inferred)}}function ii(t,e){let r=e.shipment_group;if(r===null||e.restricted)return[];let i=t.filter(n=>n.shipment_group===r&&!n.restricted).sort((n,o)=>(n.tracking_number??"").localeCompare(o.tracking_number??"","en",{numeric:!0})||pe(n,o));return i.length>1?i:[]}function Pt(t){return`.chip[data-parcels~="${CSS.escape(t)}"] button.chip-main`}function ni(t,e,r,i){let n=e?"true":"false";return l`<div class="merge-note">
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
  </div>`}function on(t,e,r){let i=r&&(t.tracking_number?.trim()??null)||null;return{title:i?`${e} ${i}`:e,detail:i}}function an(t,e,r){let{title:i,detail:n}=e;return ni({icon:"mdi:call-merge",label:s.autoMerged,detail:n,undoLabel:g(s.undoMergeLabel,{title:i}),keepLabel:g(s.keepMergeLabel,{title:i})},r.busy,()=>r.onUndoMerge(t),()=>r.onKeepMerge(t))}function ln(t,e,r){let{title:i,detail:n}=e;return ni({icon:"mdi:package-variant-closed-check",label:s.inferred,detail:n,undoLabel:g(s.undoInferredLabel,{title:i}),keepLabel:g(s.keepInferredLabel,{title:i})},r.busy,()=>r.onUndoInferred(t),()=>r.onKeepInferred(t))}function rt(t,e){let{locale:r}=e,i=e.placement??null,n=e.members&&e.members.length>1?e.members:[t],o=n.length>1,a=ri(t,n),d=w(a),c=ei(a,{locale:r,placement:i,count:n.length,continuesBefore:e.continuesBefore,continuesAfter:e.continuesAfter}),h=Xr(a,{locale:r,placement:i,count:n.length,showStatus:e.showStatus,showRange:e.showRange}),m={chip:!0,"cont-before":e.continuesBefore===!0,"cont-after":e.continuesAfter===!0,returned:a.status==="returned"},p={...e.position,"--chip-color":Ee(a.status)},f=l`<span class="chip-row" aria-hidden=${a.restricted?"true":u}>
    ${e.continuesBefore?l`<span class="cont">‹</span>`:u}
    ${a.status==="delivered"?l`<span class="check">✓</span>`:u}
    <span class="chip-text">
      <span class="chip-title">${d}</span>
      ${h?l`<span class="chip-meta">${h}</span>`:u}
    </span>
    ${a.ai&&!a.restricted?l`<span class="badge ai">${s.aiBadge}</span>`:u}
    ${a.has_code&&!a.restricted?l`<ha-icon class="lock" icon="mdi:dialpad" title=${s.hasCode}></ha-icon>`:u}
    ${a.private||a.restricted?l`<ha-icon class="lock" icon="mdi:lock"></ha-icon>`:u}
    ${e.continuesAfter?l`<span class="cont">›</span>`:u}
  </span>`;return a.restricted?l`<div class=${kt(m)} style=${M(p)}>
      <div class="chip-main" title=${c}>
        <span class="sr-only">${c}</span>
        ${f}
      </div>
    </div>`:l`<div
    class=${kt(m)}
    style=${M(p)}
    data-parcel-id=${a.id}
    data-parcels=${n.map(_=>_.id).join(" ")}
  >
    <button
      type="button"
      class="chip-main"
      aria-haspopup="dialog"
      aria-label=${c}
      title=${c}
      @click=${_=>e.onOpen(t,_.currentTarget)}
    >
      ${f}
    </button>
    ${n.map(_=>{let b=on(_,d,o);return l`${_.auto_merged?an(_,b,e):u}${_.inferred?ln(_,b,e):u}`})}
  </div>`}function S(t){return typeof t=="object"&&t!==null&&!Array.isArray(t)}function v(t){return typeof t=="string"?t:null}function y(t){return typeof t=="string"?t:""}function Z(t){return Array.isArray(t)?t.filter(e=>typeof e=="string"):[]}function X(t){return typeof t=="string"&&t!==""?t:null}function dn(t){return Number.isSafeInteger(t)&&t>0?t:0}function cn(t){return typeof t=="number"&&Number.isFinite(t)&&t>=0?t:null}function J(t,e){if(!Array.isArray(t))return[];let r=[];for(let i of t){let n=e(i);n!==null&&r.push(n)}return r}function Rt(t){return t==="ai"||t==="manual"||t==="seventeentrack"?t:"parser"}function un(t){return!S(t)||!X(t.origin)?null:{origin:y(t.origin),at:y(t.at),reason:y(t.reason)}}function it(t){if(!S(t))return null;let e=X(t.id);return e?{id:e,merchant:v(t.merchant),carrier:v(t.carrier),carrier_name:v(t.carrier_name),tracking_number:v(t.tracking_number),tracking_url:v(t.tracking_url),status:y(t.status),status_time:v(t.status_time),eta_start:v(t.eta_start),eta_end:v(t.eta_end),window_start:v(t.window_start),window_end:v(t.window_end),delivered_at:v(t.delivered_at),inferred:t.inferred===!0,pickup_point:v(t.pickup_point),pickup_code:v(t.pickup_code),has_code:t.has_code===!0,order_numbers:Z(t.order_numbers),items:Z(t.items),private:t.private===!0,owners:Z(t.owners),source:Rt(t.source),ai:t.ai===!0,auto_merged:un(t.auto_merged),provisional:t.provisional===!0,archived:t.archived===!0,origins:Z(t.origins),shipment_group:X(t.shipment_group),restricted:t.restricted===!0}:null}function pn(t){return S(t)?{kind:y(t.kind),merchant:v(t.merchant),carrier:v(t.carrier),tracking_numbers:Z(t.tracking_numbers),order_numbers:Z(t.order_numbers),eta_start:v(t.eta_start),eta_end:v(t.eta_end),window_start:v(t.window_start),window_end:v(t.window_end),pickup_point:v(t.pickup_point),pickup_code:v(t.pickup_code),items:Z(t.items)}:null}function hn(t){if(!S(t))return null;let e=X(t.id);return e?{id:e,created:y(t.created),received:v(t.received),sender:y(t.sender),sender_domain:y(t.sender_domain),subject:y(t.subject),mailbox_owner:v(t.mailbox_owner),reason:y(t.reason),authenticated:t.authenticated===!0,source:t.source==="ai"?"ai":"parser",suggestion:pn(t.suggestion)}:null}function mn(t){if(!S(t))return null;let e=X(t.id);return e?{id:e,created:y(t.created),received:v(t.received),sender:y(t.sender),sender_domain:y(t.sender_domain),subject:y(t.subject)}:null}function fn(t){if(!S(t))return null;let e=X(t.id),r=it(t.parcel),i=J(t.candidates,it);return!e||!r||!i.length?null:{id:e,reason:y(t.reason),merchant:v(t.merchant),day:W(t.day)?t.day:null,parcel:r,candidates:i}}function gn(t){return t==="suggest"||t==="auto"?t:"off"}function _n(t,e=Date.now()){let r=S(t)?t:{},i=X(r.time_zone)??"UTC",n=W(r.today)?r.today:xe(new Date(e).toISOString(),i)??"1970-01-01";return{user_is_admin:r.user_is_admin===!0,ai_enabled:r.ai_enabled===!0,ai_mode:gn(r.ai_mode),ai_queue:dn(r.ai_queue),ai_queue_seconds:cn(r.ai_queue_seconds),dashboard_url:y(r.dashboard_url),seventeentrack:r.seventeentrack===!0,time_zone:i,today:n}}function si(t,e=Date.now()){let r=S(t)?t:{};return{parcels:J(r.parcels,it),review:J(r.review,hn),merge_suggestions:J(r.merge_suggestions,fn),filtered:J(r.filtered,mn),settings:_n(r.settings,e)}}function bn(t){return S(t)?{time:y(t.time),status:y(t.status),source:t.source==="inferred"?"inferred":Rt(t.source),label:y(t.label)}:null}function vn(t){return S(t)?{id:y(t.id),merchant:v(t.merchant),number:y(t.number),placed_at:v(t.placed_at),parcel_ids:Z(t.parcel_ids)}:null}function yn(t){if(!S(t))return null;let e=X(t.id);return e?{id:e,label:y(t.label),source:Rt(t.source),time:v(t.time)}:null}function oi(t){if(!S(t))return null;let e=it(t.parcel);return e?{parcel:e,timeline:J(t.timeline,bn),orders:J(t.orders,vn),origins:J(t.origins,yn)}:null}function ai(t){if(typeof t!="string")return null;let e=t.trim();if(!e)return null;let r;try{r=new URL(e)}catch{return null}return r.protocol!=="https:"||!r.hostname||r.username||r.password?null:r.href}var $n={weekday:"short",day:"numeric",month:"short",year:"numeric"},li={eta_start:"",eta_end:"",window_start:"",window_end:""};function wn(t){return t.map((e,r)=>({entry:e,index:r,time:L(e.time)??-1/0})).sort((e,r)=>r.time-e.time||r.index-e.index).map(({entry:e})=>e)}var Mt=class extends le{static properties={snapshot:{attribute:!1},locale:{attribute:!1},_parcelId:{state:!0},_details:{state:!0},_loading:{state:!0},_loadError:{state:!0},_mode:{state:!0},_copyState:{state:!0},_dateForm:{state:!0},_formError:{state:!0},_mergeTarget:{state:!0},_splitSelection:{state:!0},_pendingPrivate:{state:!0}};static styles=[H,Ye,x`
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
    `];_request=0;_loadedKey="";constructor(){super(),this.snapshot=null,this.locale=Qe(void 0),this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._copyState="idle",this._dateForm=li,this._formError=null,this._mergeTarget="",this._splitSelection=[],this._pendingPrivate=null}async open(e,r=null){this._parcelId=e,this._details=null,this._loadError=null,this._mode="view",this._copyState="idle",this._formError=null,this._pendingPrivate=null,this._load(),await this.showDialog(r)}_switchTo(e){this._busy||e===this._parcelId||(this._parcelId=e,this._details=null,this._loadError=null,this._error=null,this._mode="view",this._copyState="idle",this._formError=null,this._pendingPrivate=null,this._load(),this.focusAfterRender("[data-current-package]"))}dialogClosed(){this._request+=1,this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._pendingPrivate=null}canLightDismiss(){return this._mode==="view"&&!this._busy}willUpdate(e){if(super.willUpdate(e),!e.has("snapshot")||!this.isOpen||!this.snapshot)return;this._pendingPrivate=null;let r=this.snapshot.parcels.find(i=>i.id===this._parcelId);r&&JSON.stringify(r)!==this._loadedKey&&this._load()}get _parcel(){let e=this._parcelId;return e===null?null:this.snapshot?this.snapshot.parcels.find(r=>r.id===e)??null:this._details?.parcel??null}async _load(){let e=this.hass,r=this._parcelId;if(!e||r===null)return;let i=++this._request,n=this.snapshot?.parcels.find(o=>o.id===r);this._loadedKey=n?JSON.stringify(n):"",this._loading=!0,this._loadError=null;try{let o=await we(e,"get",{parcel_id:r});if(i!==this._request)return;let a=oi(o);if(!a)throw new Error(s.unknownError);this._details=a}catch(o){i===this._request&&(this._loadError=A(o))}finally{i===this._request&&(this._loading=!1)}}renderContent(){let e=this._parcel;return l`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">
            ${e?w(e):s.details}
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
      ${e&&!e.restricted?this._renderActions(e):u}
    `}_renderBadges(e){return l`<div class="dialog-badges">
      <span class="badge" style=${M({"--badge-color":Ee(e.status)})}>
        ${K(e.status)}
      </span>
      ${e.ai&&!e.restricted?l`<span class="badge ai" title=${s.aiBadgeLabel}>
            ${s.aiBadge}<span class="sr-only">, ${s.aiBadgeLabel}</span>
          </span>`:u}
      ${e.private||e.restricted?l`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${s.private}
          </span>`:u}
      ${e.provisional?l`<span class="badge info">${s.provisional}</span>`:u}
      ${e.archived?l`<span class="badge">${s.archived}</span>`:u}
    </div>`}_renderBody(e){if(!e)return this.snapshot||!this._loading&&!this._loadError?l`<p class="empty">${s.notFound}</p>`:this._renderLoadState();switch(this._mode){case"date":return this._renderDateForm();case"merge":return this._renderMerge(e);case"split":return this._renderSplit();case"archive":return l`<p>${s.archiveQuestion}</p>`;default:return this._renderView(e)}}_renderLoadState(){return this._loadError?l`<div class="alert error" role="alert">
        <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
        <span class="grow">${g(s.detailsError,{message:this._loadError})}</span>
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
          </div>`:u}
      ${!r&&e.auto_merged?this._renderMergeNotice(e):u}
      ${!r&&e.inferred?this._renderInferredNotice(e):u}
      ${!r&&e.provisional?l`<p class="hint">${s.provisionalHint}</p>`:u}
      ${this._renderFacts(e)}
      ${r?u:l`<label class="check-row switch-row">
            <input
              type="checkbox"
              role="switch"
              .checked=${E(this._pendingPrivate??e.private)}
              aria-disabled=${this._busy?"true":"false"}
              @click=${this._onPrivateClick}
              @change=${this._togglePrivate}
            />
            <span>${s.fieldPrivate}</span>
          </label>`}
      <h3 class="section-title">${s.timeline}</h3>
      ${this._details?this._renderTimeline(this._details.timeline):this._renderLoadState()}
    `}_renderMergeNotice(e){let r=Je(e.auto_merged?.reason),i=this._busy?"true":"false",n=w(e);return l`<div class="alert warning">
      <ha-icon icon="mdi:call-merge" aria-hidden="true"></ha-icon>
      <span class="grow">
        ${r?g(s.mergedNotice,{reason:r}):s.mergedNoticeNoReason}
      </span>
      <button
        type="button"
        class="btn"
        aria-label=${g(s.undoMergeLabel,{title:n})}
        aria-disabled=${i}
        @click=${this._undoMerge}
      >
        ${s.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${g(s.keepMergeLabel,{title:n})}
        aria-disabled=${i}
        @click=${this._keepMerge}
      >
        ${s.keep}
      </button>
    </div>`}_renderInferredNotice(e){let r=this._busy?"true":"false",i=w(e);return l`<div class="alert warning">
      <ha-icon icon="mdi:package-variant-closed-check" aria-hidden="true"></ha-icon>
      <span class="grow">${s.inferredNotice}</span>
      <button
        type="button"
        class="btn"
        aria-label=${g(s.undoInferredLabel,{title:i})}
        aria-disabled=${r}
        @click=${this._undoInferred}
      >
        ${s.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${g(s.keepInferredLabel,{title:i})}
        aria-disabled=${r}
        @click=${this._keepInferred}
      >
        ${s.keep}
      </button>
    </div>`}_renderFacts(e){let r=this.locale,i=U(e),n=ue(e.window_start,e.window_end,r),o=Q(e),a=e.restricted?null:ai(e.tracking_url),d=e.tracking_number?.trim()??"",c=this._details?.orders??[],h=ii(this.snapshot?.parcels??[],e),m=this._details?.parcel.id===e.id?this._details.parcel:null,p=e.has_code?m?.pickup_code??null:null,f=(b,T)=>l`<div><dt>${b}</dt><dd>${T}</dd></div>`,_=e.status_time?` \xB7 ${g(s.sinceDate,{date:F(e.status_time,r)})}`:"";return l`<dl class="facts">
      ${f(s.status,`${K(e.status)}${_}`)}
      ${e.delivered_at?f(s.delivered,F(e.delivered_at,r)):u}
      ${i?f(s.expected,C(i.start,i.end,r,$n)):u}
      ${n?f(s.timeWindow,n):u}
      ${o||a||!e.restricted?f(s.carrier,l`${o??(e.restricted?"":s.notKnownYet)}${a?l`<a class="link" href=${a} target="_blank" rel="noopener noreferrer">
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
      ${h.length?f(s.packagesInShipment,l`<ul class="packages">
              ${h.map(b=>this._renderPackage(b,e.id))}
            </ul>`):u}
      ${e.merchant?f(s.merchant,e.merchant):u}
      ${c.length?f(s.orders,l`<ul>
              ${c.map(b=>l`<li>
                    ${b.number}${b.placed_at?` \xB7 ${F(b.placed_at,r)}`:""}
                  </li>`)}
            </ul>`):e.order_numbers.length?f(s.orders,e.order_numbers.join(", ")):u}
      ${e.items.length?f(s.items,l`<ul>
              ${e.items.map(b=>l`<li>${b}</li>`)}
            </ul>`):u}
      ${e.pickup_point?f(s.pickupPoint,e.pickup_point):u}
      ${p?f(s.pickupCode,p):u}
      ${e.restricted?u:f(s.parcelId,e.id)}
    </dl>`}_renderPackage(e,r){let i=this.locale,n=e.tracking_number?.trim()||w(e),o=U(e),a=e.delivered_at?F(e.delivered_at,i):o?C(o.start,o.end,i):"",d=[K(e.status),a].filter(Boolean).join(" \xB7 ");return e.id===r?l`<li aria-current="true" tabindex="-1" data-current-package>
        <strong>${n}</strong>${d?` \xB7 ${d}`:""}
      </li>`:l`<li>
      <button
        type="button"
        class="link-btn"
        aria-label=${g(s.showPackage,{name:n})}
        aria-disabled=${this._busy?"true":"false"}
        @click=${()=>this._switchTo(e.id)}
      >
        ${n}</button
      >${d?` \xB7 ${d}`:""}
    </li>`}_renderTimeline(e){if(!e.length)return l`<p class="muted">${s.noTimeline}</p>`;let r=this.locale;return l`<ol class="timeline">
      ${wn(e).map(i=>{let n=K(i.status),o=i.label.trim(),a=[F(i.time,r),Et(i.source)].filter(Boolean).join(" \xB7 ");return l`<li style=${M({"--dot-color":Ee(i.status)})}>
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
          .value=${E(e[n])}
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
    </form>`}_renderMerge(e){let r=tt(this.snapshot?.parcels??[],e.id);if(!r.length)return l`<p class="empty">${s.noMergeCandidates}</p>`;let i=this._resolvedMergeTarget(r);return l`<p>${s.mergeIntro}</p>
      <label class="field">
        <span class="field-label">${s.mergeChoose}</span>
        <select data-first @change=${this._onMergeTarget}>
          ${r.map(n=>l`<option value=${n.id} ?selected=${n.id===i}>
                ${Ae(n,this.locale)}
              </option>`)}
        </select>
      </label>`}_renderSplit(){let e=this._details?.origins??[],r=this.locale;return l`<fieldset aria-describedby="split-hint">
        <legend>${s.splitIntro}</legend>
        ${e.map((i,n)=>{let o=i.time?F(i.time,r):"";return l`<label class="check-row">
            <input
              type="checkbox"
              .value=${i.id}
              .checked=${E(this._splitSelection.includes(i.id))}
              ?data-first=${n===0}
              @change=${this._onSplitChange}
            />
            <span>
              ${i.label.trim()||Et(i.source)}${o?l`<span class="muted"> · ${o}</span>`:u}
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
        </div>`;case"merge":{let n=tt(this.snapshot?.parcels??[],e.id);return l`<div class="dialog-actions">
          ${i}
          ${n.length?l`<button
                type="button"
                class="btn primary"
                aria-disabled=${r}
                @click=${this._merge}
              >
                ${s.mergeConfirm}
              </button>`:u}
        </div>`}case"split":{let n=wt(this._splitSelection,this._details?.origins.length??0);return l`<div class="dialog-actions">
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
              </button>`:u}
          ${e.archived?u:l`<button
                type="button"
                class="btn danger"
                data-mode="archive"
                @click=${this._startArchive}
              >
                ${s.archive}
              </button>`}
          ${et(e.status)?l`<span class="spacer"></span>
                <button
                  type="button"
                  class="btn primary"
                  aria-disabled=${r}
                  @click=${this._markDelivered}
                >
                  <ha-icon icon="mdi:check" aria-hidden="true"></ha-icon>${s.markDelivered}
                </button>`:u}
        </div>`}}}_setMode(e){this._mode=e,this._error=null,this._formError=null,this.focusAfterRender(e==="archive"?"[data-cancel]":"[data-first], [data-cancel]")}_backToView(){let e=this._mode;this._mode="view",this._error=null,this._formError=null,this.focusAfterRender(`[data-mode="${e}"]`)}_editDate(){let e=this._parcel;this._dateForm=e?Ir(e):li,this._setMode("date")}_startMerge(){this._mergeTarget="",this._setMode("merge")}_startSplit(){this._splitSelection=[],this._setMode("split")}_startArchive(){this._setMode("archive")}_parcelService(e,r,i){let n=this.hass,o=this._parcel;!n||!o||this.runAction(()=>Y(n,e,{parcel_id:o.id,...r}),i)}_confirm(){this._parcelService("update",{confirm:!0})}_undoMerge(){this._parcelService("undo_merge",{})}_keepMerge(){this._parcelService("update",{confirm_merge:!0})}_undoInferred(){this._parcelService("undo_delivery",{})}_keepInferred(){this._parcelService("update",{confirm_delivery:!0})}_markDelivered(){this._parcelService("mark_delivered",{})}_archive(){this._parcelService("archive",{},()=>this.closeDialog())}_onPrivateClick(e){this._busy&&e.preventDefault()}_togglePrivate(e){let r=e.currentTarget.checked,i=this.hass,n=this._parcel;!i||!n||this._busy||(this._pendingPrivate=r,this.runAction(async()=>{try{await Y(i,"update",{parcel_id:n.id,private:r})}catch(o){throw this._pendingPrivate=null,o}}))}_onDateInput(e){let r=e.currentTarget,i=r.name;this._dateForm={...this._dateForm,[i]:r.value},this._formError=null}_saveDate(e){e.preventDefault();let r=this._parcel;if(!r||this._busy)return;let i=this._dateForm,n=qe(i);if(n){this._formError=n,this.focusAfterRender(`[name="${n.field}"]`);return}let o=Lr(r.id,i);this._parcelService("update",o,()=>this._backToView())}_resolvedMergeTarget(e){return e.some(r=>r.id===this._mergeTarget)?this._mergeTarget:e[0]?.id??""}_onMergeTarget(e){this._mergeTarget=e.currentTarget.value}_merge(){let e=this.hass,r=this._parcel;if(!e||!r)return;let i=this._resolvedMergeTarget(tt(this.snapshot?.parcels??[],r.id));i&&this.runAction(()=>Y(e,"merge",{parcel_ids:[r.id,i]}),()=>this._backToView())}_onSplitChange(e){let r=e.currentTarget,i=this._splitSelection.filter(n=>n!==r.value);this._splitSelection=r.checked?[...i,r.value]:i}_split(){let e=this._details?.origins.length??0;wt(this._splitSelection,e)&&this._parcelService("split",{origins:[...this._splitSelection]},()=>this._backToView())}async _copy(e){let r=e.currentTarget,i=this._parcel?.tracking_number?.trim();if(!i)return;this._copyState="idle";try{if(!navigator.clipboard?.writeText)throw new Error("Clipboard API unavailable");await navigator.clipboard.writeText(i),this._copyState="copied";return}catch{}let n=this.renderRoot.querySelector("#tracking-number");n?.focus(),n?.select();let o=!1;try{o=document.execCommand("copy")}catch{o=!1}this._copyState=o?"copied":"failed",o&&r.focus()}};N("parcels-details-dialog",Mt);var xn="parcels/subscribe",di=[2e3,1e4,3e4,6e4,3e5],nt=new Map,kn=0;function ui(t,e){try{t(e)}catch(r){console.error(r)}}function ci(t,e){t.state=e;for(let r of[...t.listeners.values()])ui(r,e)}function pi(t){try{t().catch(()=>{})}catch{}}function ot(t){t.retryTimer!==void 0&&(clearTimeout(t.retryTimer),t.retryTimer=void 0)}function st(t){t.connection.removeEventListener("ready",t.onReady),t.connection.removeEventListener("disconnected",t.onDisconnected)}function Sn(t){ot(t);let e=di[Math.min(t.retries,di.length-1)]??3e5;t.retries+=1,t.retryTimer=setTimeout(()=>{t.retryTimer=void 0,It(t)},e)}function It(t){if(t.released||t.unsubscribe||t.pending||t.listeners.size===0)return;ot(t);let e=++t.attempt,r=t.epoch,i=()=>!t.released&&t.attempt===e;t.pending=!0;let n;try{n=t.connection.subscribeMessage(o=>{i()&&(t.retries=0,ci(t,{snapshot:si(o),error:null}))},{type:xn},{resubscribe:!1})}catch(o){n=Promise.reject(o)}n.then(o=>{if(i()){t.pending=!1,t.unsubscribe=o;return}t.epoch===r&&pi(o),t.released&&t.attempt===e+1&&(t.pending=!1,st(t))},o=>{i()?(t.pending=!1,ci(t,{snapshot:t.state.snapshot,error:A(o)}),Sn(t)):t.released&&t.attempt===e+1&&(t.pending=!1,st(t))})}function Tn(t,e){if(!t.listeners.delete(e)||t.listeners.size>0)return;t.released=!0,t.attempt+=1,ot(t),nt.get(t.connection)===t&&nt.delete(t.connection);let r=t.unsubscribe;t.unsubscribe=null,r&&pi(r),t.pending||st(t)}function En(t){let e={connection:t,listeners:new Map,state:{snapshot:null,error:null},epoch:0,attempt:0,unsubscribe:null,pending:!1,released:!1,retries:0,retryTimer:void 0,onReady:()=>{e.released||e.unsubscribe||(e.pending=!1,e.retries=0,It(e))},onDisconnected:()=>{e.epoch+=1,e.attempt+=1,e.unsubscribe=null,e.pending=!1,ot(e),e.released&&st(e)}};return e}function hi(t,e){let r=++kn,i=nt.get(t);i?(i.listeners.set(r,e),(i.state.snapshot||i.state.error)&&ui(e,i.state)):(i=En(t),nt.set(t,i),i.listeners.set(r,e),t.addEventListener("ready",i.onReady),t.addEventListener("disconnected",i.onDisconnected),It(i));let n=i,o=!0;return()=>{o&&(o=!1,Tn(n,r))}}var at=class{snapshot=null;error=null;_host;_connection=null;_unsubscribe=null;_hostConnected=!1;constructor(e){this._host=e,e.addController(this)}setConnection(e){e!==this._connection&&(this._release(),this._connection=e,this.snapshot=null,this.error=null,this._hostConnected&&this._subscribe(),this._host.requestUpdate())}hostConnected(){this._hostConnected=!0,this._subscribe()}hostDisconnected(){this._hostConnected=!1,this._release()}_subscribe(){!this._connection||this._unsubscribe||(this._unsubscribe=hi(this._connection,e=>{this.snapshot=e.snapshot??this.snapshot,this.error=e.error,this._host.requestUpdate()}))}_release(){let e=this._unsubscribe;this._unsubscribe=null,e?.()}};var Ce=class extends P{static properties={_actionError:{state:!0}};_snapshots=new at(this);_hass=void 0;_hassKey=null;_locale=null;_localeKey="";constructor(){super(),this._actionError=null}get hass(){return this._hass}set hass(e){this._hass=e,this._snapshots.setConnection(e?.connection??null),this.toggleAttribute("dark",e?.themes?.darkMode===!0);let r=JSON.stringify([e?.language,e?.locale?.language,e?.locale?.time_format,e?.locale?.time_zone,e?.config?.time_zone,e?.user?.is_admin,e?.themes?.darkMode]);r!==this._hassKey&&(this._hassKey=r,this.requestUpdate()),this.hassChanged()}hassChanged(){}get snapshot(){return this._snapshots.snapshot}get locale(){let e=this._snapshots.snapshot?.settings.time_zone,r=`${this._hassKey??""}|${e??""}`;return(!this._locale||r!==this._localeKey)&&(this._locale=Qe(this._hass,e),this._localeKey=r),this._locale}async callService(e,r,i){let n=this._hass;if(!n)return!1;this._actionError=null;try{return await Y(n,e,r),!0}catch(o){return this._actionError=g(i,{message:A(o)}),!1}}renderBanners(){let{snapshot:e,error:r}=this._snapshots;return!r&&!this._actionError?u:l`<div class="banners">
      ${r?l`<div class="alert ${e?"warning":"error"}" role="alert">
            <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              ${g(e?s.refreshError:s.loadError,{message:r})}
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
    </div>`}renderLoading(){return this._snapshots.error?u:l`<p class="empty" role="status">${s.loading}</p>`}showActionError(e){this._actionError=e}_dismissActionError(){this._actionError=null}},he=class extends Ce{static properties={_busyParcels:{state:!0}};_focusedParcel=null;constructor(){super(),this._busyParcels=new Set}willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement;this._focusedParcel=r instanceof HTMLElement?r.closest(".chip[data-parcel-id]")?.dataset.parcelId??null:null}updated(e){super.updated(e);let r=this._focusedParcel;this._focusedParcel=null,r!==null&&!this.shadowRoot?.activeElement&&Lt()&&this.renderRoot.querySelector(Pt(r))?.focus()}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback], button.chip-main")}openDetails=(e,r)=>{this.renderRoot.querySelector("parcels-details-dialog")?.open(e.id,()=>{(r.isConnected?r:this.renderRoot.querySelector(Pt(e.id))??this.focusFallback())?.focus()})};undoMerge=e=>{this._parcelAction(e.id,"undo_merge",{parcel_id:e.id},s.undoFailed)};keepMerge=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_merge:!0},s.keepFailed)};undoInferred=e=>{this._parcelAction(e.id,"undo_delivery",{parcel_id:e.id},s.undoInferredFailed)};keepInferred=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_delivery:!0},s.keepInferredFailed)};renderDetailsDialog(){return l`<parcels-details-dialog
      .hass=${this.hass}
      .snapshot=${this.snapshot}
      .locale=${this.locale}
      @parcels-error=${this._onDialogError}
    ></parcels-details-dialog>`}async _parcelAction(e,r,i,n){if(!this._busyParcels.has(e)){this._busyParcels=new Set([...this._busyParcels,e]);try{await this.callService(r,i,n)}finally{let o=new Set(this._busyParcels);o.delete(e),this._busyParcels=o}}}_onDialogError(e){this.showActionError(e.detail)}};function Lt(){let t=document.activeElement;return!t||t===document.body}function Dt(t){if(typeof t!="object"||t===null||Array.isArray(t))throw new Error(s.configInvalid);return t}function Ot(t){let e=t.title;if(e!=null){if(typeof e!="string")throw new Error(s.configTitle);return e.trim()}}function Nt(t){return typeof t.type=="string"?t.type:""}function Ht(t){let e=Dt(t),r=e.show_archived??!0;if(typeof r!="boolean")throw new Error(s.configShowArchived);return{type:Nt(e),title:Ot(e),show_archived:r}}function Ft(t){let e=Dt(t);return{type:Nt(e),title:Ot(e)}}function Ut(t){let e=Dt(t);return{type:Nt(e),title:Ot(e)}}function me(t,e){return t===void 0?e:t||null}function An(t,e){let r=xe(t.status_time,e.timeZone);switch(t.status){case"cancelled":return null;case"delivered":{let n=xe(t.delivered_at,e.timeZone)??r;return n?{kind:"delivered",from:n,to:n}:null}case"returned":return r?{kind:"returned",from:r,to:r}:null;case"ready_for_pickup":{let n=r??e.today;return{kind:"pickup",from:n,to:Rr(n,e.today)}}default:break}let i=U(t);return i?{kind:"eta",from:i.start,to:i.end}:(t.status==="attempted"||t.status==="exception")&&r?{kind:"status",from:r,to:r}:null}function mi(t){return t.window_start??t.window_end??"~"}function Bt(t,e){return t<e?-1:t>e?1:0}function Cn(t,e){return t.startCol-e.startCol||e.endCol-e.startCol-(t.endCol-t.startCol)||Bt(mi(t.parcel),mi(e.parcel))||Bt(w(t.parcel).toLowerCase(),w(e.parcel).toLowerCase())||Bt(t.parcel.id,e.parcel.id)}function fi(t,e,r,i){let n=Pr(e),o=de(e,6),a=[];for(let m of t){if(m.archived&&!i.showArchived)continue;let p=An(m,r);!p||I(p.to,e)<0||I(p.from,o)>0||a.push({parcel:m,members:[m],placement:p,startCol:Math.max(0,yt(e,p.from)),endCol:Math.min(6,yt(e,p.to)),continuesBefore:I(p.from,e)<0,continuesAfter:I(p.to,o)>0,lane:0})}let d=At(a,m=>Ct(m.parcel,m.placement.kind,m.placement.from,m.placement.to)).map(m=>({...m.reduce((f,_)=>pe(_.parcel,f.parcel)<0?_:f),members:m.map(f=>f.parcel).sort(pe)}));d.sort(Cn);let c=[];for(let m of d){let p=c.findIndex(f=>f<m.startCol);p===-1&&(p=c.length),c[p]=m.endCol,m.lane=p}let h=n.map((m,p)=>d.filter(f=>f.startCol<=p&&p<=f.endCol).sort((f,_)=>f.lane-_.lane));return{start:e,end:o,days:n,items:d,lanes:c.length,perDay:h,busy:h.map(m=>m.length>0)}}var Pn=600,Rn=616,Mn={weekday:"short"},In={day:"numeric"},Ln={weekday:"long",day:"numeric",month:"long"},Dn={weekday:"long",day:"numeric",month:"short"},zt=class extends he{static properties={_config:{state:!0},_weekOffset:{state:!0},_narrow:{state:!0},_refreshing:{state:!0}};static styles=[H,Ve,x`
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
    `];_resizeObserver=null;_resizeFrame=0;_layoutCache=null;constructor(){super(),this._config=Ht({}),this._weekOffset=0,this._narrow=!1,this._refreshing=!1}static getStubConfig(){return{}}setConfig(e){this._config=Ht(e)}getCardSize(){let e=this._layout();return e?this._narrow?9+e.perDay.reduce((i,n)=>i+n.length,0):3+Math.max(1,e.lanes):4}getGridOptions(){return{columns:"full",rows:"auto",min_columns:6}}connectedCallback(){super.connectedCallback(),typeof ResizeObserver<"u"&&(this._resizeObserver??=new ResizeObserver(e=>{let r=e[e.length-1]?.contentRect.width??0;cancelAnimationFrame(this._resizeFrame),this._resizeFrame=requestAnimationFrame(()=>this._measure(r))}),this._resizeObserver.observe(this))}disconnectedCallback(){super.disconnectedCallback(),this._resizeObserver?.disconnect(),cancelAnimationFrame(this._resizeFrame)}firstUpdated(e){super.firstUpdated(e),this._measure(this.getBoundingClientRect().width)}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback]")}_measure(e){e<=0||(e<Pn?this._narrow=!0:e>=Rn&&(this._narrow=!1))}_monday(e){return de(Cr(e.settings.today),7*this._weekOffset)}_layout(){let e=this.snapshot;if(!e)return null;let r=this._monday(e),i=this._config.show_archived,n=this._layoutCache;if(n&&n.snapshot===e&&n.monday===r&&n.showArchived===i)return n.layout;let o=fi(e.parcels,r,{today:e.settings.today,timeZone:e.settings.time_zone},{showArchived:i});return this._layoutCache={snapshot:e,monday:r,showArchived:i,layout:o},o}render(){let e=this.snapshot,r=this._layout(),i=me(this._config.title,s.defaultWeekTitle),n=r?C(r.start,r.end,this.locale,Br):"";return l`<ha-card>
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
        ${this.renderBanners()}
        ${e&&r?this._narrow?this._renderStacked(e,r,n):this._renderGrid(e,r,n):l`<div class="content">${this.renderLoading()}</div>`}
      </ha-card>
      ${this.renderDetailsDialog()}
      <parcels-add-dialog
        .hass=${this.hass}
        @parcels-error=${this._onAddError}
      ></parcels-add-dialog>`}_renderGrid(e,r,i){let n=this.locale,o=e.settings.today,a=r.items.length===0,c={"grid-template-columns":r.busy.map(h=>h||a?"minmax(0, 1fr)":"minmax(0, 0.6fr)").join(" "),"grid-template-rows":`auto repeat(${Math.max(1,r.lanes)}, auto)`};return l`<div
      class="grid"
      role="group"
      aria-label=${g(s.weekOf,{range:i})}
      style=${M(c)}
    >
      ${r.days.map((h,m)=>l`<div
            class="day-bg ${h===o?"today":""}"
            style=${M({"grid-column":String(m+1)})}
            aria-hidden="true"
          ></div>`)}
      ${r.days.map((h,m)=>l`<div
            class="day-head ${h===o?"today":""}"
            style=${M({"grid-column":String(m+1)})}
            aria-current=${h===o?"date":u}
          >
            <span class="dow" aria-hidden="true">${se(h,n,Mn)}</span>
            <span class="dom" aria-hidden="true">${se(h,n,In)}</span>
            <span class="sr-only">${se(h,n,Ln)}</span>
          </div>`)}
      ${a?l`<p class="week-empty">${s.noDeliveriesThisWeek}</p>`:u}
      ${j(r.items,h=>h.parcel.id,h=>this._chip(h,!1,{"grid-column":`${h.startCol+1} / ${h.endCol+2}`,"grid-row":String(h.lane+2)}))}
    </div>`}_renderStacked(e,r,i){let n=this.locale,o=e.settings.today;return l`<ol class="days" aria-label=${g(s.weekOf,{range:i})}>
      ${r.days.map((a,d)=>{let c=r.perDay[d]??[],h=a===o;return l`<li
          class="day ${c.length?"":"compact"} ${h?"today":""}"
          aria-current=${h?"date":u}
        >
          <p class="day-label">
            ${se(a,n,Dn)}${h?l`<span class="badge info">${s.todayTag}</span>`:u}
          </p>
          ${c.length?l`<ul class="day-chips">
                ${j(c,m=>m.parcel.id,m=>l`<li>${this._chip(m,!0,void 0,d)}</li>`)}
              </ul>`:l`<span class="muted">${s.noDeliveriesThisDay}</span>`}
        </li>`})}
    </ol>`}_chip(e,r,i,n){let o=e.continuesBefore&&(!r||n===e.startCol),a=e.continuesAfter&&(!r||n===e.endCol);return rt(e.parcel,{locale:this.locale,placement:e.placement,continuesBefore:o,continuesAfter:a,showRange:r,members:e.members,busy:e.members.some(d=>this._busyParcels.has(d.id)),position:i,onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge,onUndoInferred:this.undoInferred,onKeepInferred:this.keepInferred})}_previousWeek(){this._weekOffset-=1}_nextWeek(){this._weekOffset+=1}_thisWeek(){this._weekOffset=0}async _refresh(){if(!this._refreshing){this._refreshing=!0;try{await this.callService("refresh",{},s.refreshFailed)}finally{this._refreshing=!1}}}_openAdd(e){let r=e.currentTarget;this.renderRoot.querySelector("parcels-add-dialog")?.open(()=>{r.isConnected&&r.focus()})}_onAddError(e){this.showActionError(e.detail)}};N("parcels-week-card",zt);ce("parcels-week-card",s.weekCardName,s.weekCardDescription);var jt=class extends he{static properties={_config:{state:!0}};static styles=[H,Ve,x`
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
    `];_listCache=null;constructor(){super(),this._config=Ft({})}static getStubConfig(){return{}}setConfig(e){this._config=Ft(e)}getCardSize(){let e=this._boxes();return e?1+Math.max(1,e.length):3}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}focusFallback(){return this.renderRoot.querySelector("button.chip-main")??this.renderRoot.querySelector(".content")}_boxes(){let e=this.snapshot;return e?(this._listCache?.snapshot!==e&&(this._listCache={snapshot:e,boxes:ti(Gr(e.parcels))}),this._listCache.boxes):null}render(){let e=this._boxes(),r=me(this._config.title,s.defaultListTitle);return l`<ha-card>
        ${r?l`<div class="header"><h2 class="title">${r}</h2></div>`:u}
        ${this.renderBanners()}
        <div class="content" tabindex="-1">
          ${e?this._renderList(e):this.renderLoading()}
        </div>
      </ha-card>
      ${this.renderDetailsDialog()}`}_renderList(e){if(!e.length)return l`<p class="empty">${s.noUndatedParcels}</p>`;let r=this.locale;return l`<ul class="list">
      ${j(e,i=>i.parcel.id,({parcel:i,members:n})=>l`<li>
            ${rt(i,{locale:r,showStatus:!0,members:n,busy:n.some(o=>this._busyParcels.has(o.id)),onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge,onUndoInferred:this.undoInferred,onKeepInferred:this.keepInferred})}
          </li>`)}
    </ul>`}};N("parcels-list-card",jt);ce("parcels-list-card",s.listCardName,s.listCardDescription);function On(t,e,r){let i=t.get(e);return i==="pending"||i!==void 0&&i===r}function lt(t,e,r){if(!e.size)return t;let i=t.filter(n=>!On(e,n.id,r));return i.length===t.length?t:i}function Wt(t,e){let r=new Map(t);for(let i of e)r.set(i,"pending");return r}function Kt(t,e){let r=new Map(t);for(let i of e)r.delete(i);return r}function qt(t,e,r,i){let n=new Map(t);for(let o of e)r&&i(o)?n.set(o,r):n.delete(o);return n}function gi(t,e){let r=null;for(let[i,n]of t)n!=="pending"&&n!==e&&(r??=new Map(t),r.delete(i));return r??t}function _i(t,e){if(t<=0)return null;let r=t===1?s.aiQueueOne:g(s.aiQueueMany,{count:t});if(e===null)return r;let i=Math.max(1,Math.round(e/60));return i<120?g(s.aiQueueMinutes,{queue:r,minutes:i}):g(s.aiQueueHours,{queue:r,hours:Math.round(i/60)})}var fe=["review","filtered"],Nn=new Set(["not_parcel","unknown"]),Hn={weekday:"short",day:"numeric",month:"short"};function bi(t){return L(t.received??t.created)??-1/0}function vi(t){return[...t].sort((e,r)=>bi(r)-bi(e)||(e.id<r.id?-1:e.id>r.id?1:0))}function Fn(t){return[...t].sort((e,r)=>(r.day??"").localeCompare(e.day??"")||(e.id<r.id?-1:e.id>r.id?1:0))}function Vt(t,e){if(!t.has(e))return t;let r=new Map(t);return r.delete(e),r}var Yt=class extends Ce{static properties={_config:{state:!0},_tab:{state:!0},_editing:{state:!0},_editForm:{state:!0},_editProblem:{state:!0},_busyItems:{state:!0},_itemErrors:{state:!0},_hidden:{state:!0},_confirmClearAll:{state:!0}};static styles=[H,x`
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
    `];connectedWhileHidden=!0;_focusedItem=null;_listCache=null;_visibleCache=null;_clearingAll=!1;constructor(){super(),this._config=Ut({}),this._tab="review",this._editing=null,this._editForm=$t(null),this._editProblem=null,this._busyItems=new Set,this._itemErrors=new Map,this._hidden=new Map,this._confirmClearAll=!1}static getStubConfig(){return{}}setConfig(e){this._config=Ut(e)}getCardSize(){if(!this._visible())return 0;let e=this._visibleLists();if(!e)return 3;let r=this._tab==="review"?e.review.length+e.suggestions.length:e.filtered.length;return 2+2*Math.max(1,r)}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}hassChanged(){this._syncVisibility()}_visible(){let e=this.snapshot;return e?e.settings.user_is_admin:this.hass?.user?.is_admin===!0}_syncVisibility(){let e=!this._visible();this.hidden!==e&&(this.hidden=e,this.dispatchEvent(new CustomEvent("card-visibility-changed",{bubbles:!0,composed:!0,detail:{value:!e}})))}_lists(){let e=this.snapshot;return e?(this._listCache?.snapshot!==e&&(this._listCache={snapshot:e,review:vi(e.review),suggestions:Fn(e.merge_suggestions),filtered:vi(e.filtered)}),this._listCache):null}_visibleLists(){let e=this._lists();if(!e)return null;let r=this._hidden;if(this._visibleCache?.lists!==e||this._visibleCache.hidden!==r){let i=this.snapshot;this._visibleCache={lists:e,hidden:r,visible:{review:lt(e.review,r,i),suggestions:lt(e.suggestions,r,i),filtered:lt(e.filtered,r,i)}}}return this._visibleCache.visible}_listed(e){let r=this._lists();return r?[...r.review,...r.suggestions,...r.filtered].some(i=>i.id===e):!1}willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement,i=r instanceof HTMLElement?r.closest("[data-item-id]"):null;if(i){let o=[...this.renderRoot.querySelectorAll("[data-item-id]")].filter(a=>!a.closest("[hidden]"));this._focusedItem={id:i.dataset.itemId??"",index:o.indexOf(i)}}else this._focusedItem=null;this._hidden=gi(this._hidden,this.snapshot),this._confirmClearAll&&!this._visibleLists()?.filtered.length&&(this._confirmClearAll=!1,r instanceof HTMLElement&&r.closest(".confirm")&&this._focusAfterUpdate("#panel-filtered"));let n=this._lists();if(n){let o=new Set([...n.review,...n.suggestions,...n.filtered].map(a=>a.id));this._editing!==null&&!o.has(this._editing)&&(this._editing=null,this._editProblem=null);for(let a of this._itemErrors.keys())o.has(a)||(this._itemErrors=Vt(this._itemErrors,a))}}updated(e){super.updated(e),this._syncVisibility();let r=this._focusedItem;if(this._focusedItem=null,!r||this.shadowRoot?.activeElement||!Lt())return;let n=[...this.renderRoot.querySelector(`#panel-${this._tab}`)?.querySelectorAll("[data-item-id]")??[]];(n.find(a=>a.dataset.itemId===r.id)??n[Math.min(Math.max(r.index,0),n.length-1)]??this.renderRoot.querySelector(`#tab-${this._tab}`))?.focus()}render(){if(!this._visible())return u;let e=this._visibleLists(),r=me(this._config.title,s.defaultReviewTitle);return l`<ha-card>
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
    </ha-card>`}_renderTabs(e,r){let i=n=>g(s.tabCount,{label:n==="review"?s.tabReview:s.tabFiltered,count:n==="review"?e:r});return l`<div
      class="tabs"
      role="tablist"
      aria-label=${s.reviewTabs}
      @keydown=${this._onTabKeyDown}
    >
      ${fe.map(n=>{let o=this._tab===n;return l`<button
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
    </div>`}_renderReviewList(e,r){let i=this.snapshot?.settings,n=i?_i(i.ai_queue,i.ai_queue_seconds):null,o=n?l`<p class="hint queue-hint">${n}</p>`:u;return!e.length&&!r.length?l`${o}<p class="empty">${s.emptyReview}</p>`:l`${o}<div class="items">
      ${j(r,a=>a.id,(a,d)=>this._renderMergeSuggestion(a,d))}
      ${j(e,a=>a.id,(a,d)=>this._renderReviewItem(a,d))}
    </div>`}_renderMergeSuggestion(e,r){let i=this.locale,o=this._busyItems.has(e.id)?"true":"false",a=`suggestion-subject-${r}`,d=w(e.parcel),c=Je(e.reason);return l`<article
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
        ${g(s.suggestionTitle,{parcel:Ae(e.parcel,i)})}
      </h3>
      ${c?l`<p class="meta">${g(s.reasonIs,{reason:c})}</p>`:u}
      <p class="hint">${s.suggestionHint}</p>
      <ul class="candidates">
        ${e.candidates.map(h=>{let m=Ae(h,i),p=[h.order_numbers.join(", "),h.items.join(", ")].filter(Boolean).join(" \xB7 ");return l`<li class="candidate">
            <span class="grow">
              <span class="block">${m}</span>
              ${p?l`<span class="meta block">${p}</span>`:u}
            </span>
            <button
              type="button"
              class="btn"
              aria-label=${g(s.mergeSuggestedLabel,{candidate:m,title:d})}
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
          aria-label=${g(s.keepApartLabel,{title:d})}
          aria-disabled=${o}
          @click=${()=>this._command(e.id,"suggestion/dismiss",{suggestion_id:e.id})}
        >
          ${s.keepApart}
        </button>
      </div>
    </article>`}_renderFilteredList(e){return l`<p class="hint filtered-hint">${s.filteredHint}</p>
      ${e.length?l`${this._renderClearAll()}
            <div class="items">
            ${j(e,r=>r.id,(r,i)=>this._renderFilteredItem(r,i))}
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
        </div>`:u}_renderReviewItem(e,r){let i=this.locale,n=this._busyItems.has(e.id),o=this._editing===e.id,a=`review-subject-${r}`,d=e.received??e.created,c=jr(e.reason),h=[d?g(s.receivedOn,{date:F(d,i)}):"",e.mailbox_owner?g(s.mailboxOf,{owner:e.mailbox_owner}):"",c?g(s.reasonIs,{reason:c}):""].filter(Boolean),m=e.source==="ai"?l`<span class="badge ai" title=${s.aiSuggestionLabel}>
            ${s.aiBadge}<span class="sr-only">, ${s.aiSuggestionLabel}</span>
          </span>`:u;return l`<article
      class="item"
      tabindex="-1"
      data-item-id=${e.id}
      aria-labelledby=${a}
      aria-busy=${n?"true":"false"}
    >
      ${this._renderHead(e,a,m)}
      ${h.length?l`<p class="meta">${h.join(" \xB7 ")}</p>`:u}
      ${e.authenticated?u:l`<div class="alert warning">
            <ha-icon icon="mdi:shield-alert-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              <strong class="block">${s.unverifiedSender}</strong>
              ${s.unverifiedSenderHint}
            </span>
          </div>`}
      ${o?this._renderEditForm(e,n):this._renderSuggestion(e.suggestion)}
      ${this._renderError(e.id)} ${o?u:this._renderReviewActions(e,n)}
    </article>`}_renderSuggestion(e){if(!e)return l`<p class="hint section-label">${s.noSuggestion}</p>`;let r=this.locale,i=U(e),n=[[s.fieldKind,Tt(e.kind)||null],[s.fieldMerchant,e.merchant],[s.fieldCarrier,Q({carrier:e.carrier,carrier_name:null})],[s.fieldTrackingNumbers,e.tracking_numbers.join(", ")||null],[s.fieldOrderNumbers,e.order_numbers.join(", ")||null],[s.expected,i?C(i.start,i.end,r,Hn):null],[s.timeWindow,ue(e.window_start,e.window_end,r)],[s.pickupPoint,e.pickup_point],[s.pickupCode,e.pickup_code],[s.items,e.items.length?l`<ul>
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
      <button
        type="button"
        class="btn"
        title=${g(s.trustSenderHint,{domain:n})}
        aria-disabled=${i}
        @click=${()=>this._command(e.id,"review/trust_sender",{review_id:e.id},{hide:!1})}
      >
        ${s.trustSender}
      </button>
      <button
        type="button"
        class="btn danger"
        title=${g(s.ignoreSenderHint,{domain:n})}
        aria-disabled=${i}
        @click=${()=>this._command(e.id,"review/ignore_sender",{review_id:e.id})}
      >
        ${s.ignoreSender}
      </button>
    </div>`}_renderEditForm(e,r){let i=this._editForm,n=this._editProblem,o=Object.keys(ze).filter(c=>!Nn.has(c)||c===i.kind);o.includes(i.kind)||o.unshift(i.kind);let a=Be();i.carrier&&!Object.hasOwn(G,i.carrier)&&a.unshift({id:i.carrier,name:i.carrier});let d=(c,h,m="text",p)=>{let f=n?.field===c,_=[f?"edit-error":"",p??""].filter(Boolean).join(" ");return l`<label class="field">
        <span class="field-label">${h}</span>
        <input
          type=${m}
          name=${c}
          autocomplete="off"
          .value=${E(i[c])}
          aria-invalid=${f?"true":"false"}
          aria-describedby=${_||u}
          @input=${this._onEditInput}
        />
      </label>`};return l`<form id="edit-form" class="edit-form" novalidate @submit=${this._submitEdit}>
      <div class="form-grid">
        <label class="field">
          <span class="field-label">${s.fieldKind}</span>
          <select name="kind" data-first @change=${this._onEditInput}>
            ${o.map(c=>l`<option value=${c} ?selected=${c===i.kind}>
                  ${Tt(c)||c}
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
            .value=${E(i.items)}
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
            ${g(s.receivedOn,{date:F(n,this.locale)})}
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
    </article>`}_selectTab(e,r){this._tab=e,r&&this.updateComplete.then(()=>this.renderRoot.querySelector(`#tab-${e}`)?.focus())}_onTabClick(e){let r=e.currentTarget.dataset.tab;this._selectTab(r,!1)}_onTabKeyDown(e){let r=fe.indexOf(this._tab),i=getComputedStyle(e.currentTarget).direction==="rtl",n;switch(e.key){case"ArrowRight":n=r+(i?-1:1);break;case"ArrowLeft":n=r+(i?1:-1);break;case"Home":n=0;break;case"End":n=fe.length-1;break;default:return}e.preventDefault();let o=fe[(n+fe.length)%fe.length];o&&this._selectTab(o,!0)}_focusAfterUpdate(e){this.updateComplete.then(()=>this.renderRoot.querySelector(e)?.focus())}_askClearAll(){this._confirmClearAll=!0,this._focusAfterUpdate("#clear-all-cancel")}_cancelClearAll(){this._confirmClearAll=!1,this._focusAfterUpdate("#clear-all")}_onConfirmKeyDown(e){e.key==="Escape"&&(e.preventDefault(),e.stopPropagation(),this._cancelClearAll())}async _clearAll(){let e=this.hass,r=this._visibleLists()?.filtered.map(i=>i.id)??[];if(!(!e||this._clearingAll||!r.length)){this._clearingAll=!0,this._confirmClearAll=!1,this._hidden=Wt(this._hidden,r),this._focusAfterUpdate("#panel-filtered");try{await we(e,"filtered/clear_all"),this._hidden=qt(this._hidden,r,this.snapshot,i=>this._listed(i))}catch(i){this._hidden=Kt(this._hidden,r),this.showActionError(g(s.actionFailed,{message:A(i)}))}finally{this._clearingAll=!1}}}_focusInItem(e,r){this.updateComplete.then(()=>{let i=this.renderRoot.querySelector(`[data-item-id="${CSS.escape(e)}"]`);(i?.querySelector(r)??i)?.focus()})}_startEdit(e){this._busyItems.has(e.id)||(this._editing=e.id,this._editForm=$t(e.suggestion),this._editProblem=null,this._itemErrors=Vt(this._itemErrors,e.id),this._focusInItem(e.id,"[data-first]"))}_cancelEdit(e){this._editing=null,this._editProblem=null,this._focusInItem(e,"[data-edit]")}_onEditInput(e){let r=e.currentTarget,i=r.name;this._editForm={...this._editForm,[i]:r.value},this._editProblem=null}_submitEdit(e){e.preventDefault();let r=this._editing;if(r===null||this._busyItems.has(r))return;let i=qe(this._editForm);if(i){this._editProblem=i,this._focusInItem(r,`[name="${i.field}"]`);return}this._command(r,"review/accept",{review_id:r,overrides:Or(this._editForm)},{onSuccess:()=>{this._editing===r&&(this._editing=null)}})}_accept(e){this._command(e.id,"review/accept",{review_id:e.id})}async _command(e,r,i,{hide:n=!0,onSuccess:o}={}){let a=this.hass;if(!(!a||this._busyItems.has(e)||this._hidden.has(e))){this._busyItems=new Set([...this._busyItems,e]),this._itemErrors=Vt(this._itemErrors,e),n&&(this._hidden=Wt(this._hidden,[e]));try{await we(a,r,i),n&&(this._hidden=qt(this._hidden,[e],this.snapshot,d=>this._listed(d))),o?.()}catch(d){this._hidden=Kt(this._hidden,[e]);let c=g(s.actionFailed,{message:A(d)});this._listed(e)?this._itemErrors=new Map([...this._itemErrors,[e,c]]):this.showActionError(c)}finally{let d=new Set(this._busyItems);d.delete(e),this._busyItems=d}}}};N("parcels-review-card",Yt);ce("parcels-review-card",s.reviewCardName,s.reviewCardDescription);
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
