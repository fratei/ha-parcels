var Ge=globalThis,Ye=Ge.ShadowRoot&&(Ge.ShadyCSS===void 0||Ge.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,Pt=Symbol(),xr=new WeakMap,Le=class{constructor(e,r,i){if(this._$cssResult$=!0,i!==Pt)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=r}get styleSheet(){let e=this.o,r=this.t;if(Ye&&e===void 0){let i=r!==void 0&&r.length===1;i&&(e=xr.get(r)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&xr.set(r,e))}return e}toString(){return this.cssText}},Sr=t=>new Le(typeof t=="string"?t:t+"",void 0,Pt),x=(t,...e)=>{let r=t.length===1?t[0]:e.reduce((i,n,o)=>i+(a=>{if(a._$cssResult$===!0)return a.cssText;if(typeof a=="number")return a;throw Error("Value passed to 'css' function must be a 'css' function result: "+a+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(n)+t[o+1],t[0]);return new Le(r,t,Pt)},Rr=(t,e)=>{if(Ye)t.adoptedStyleSheets=e.map(r=>r instanceof CSSStyleSheet?r:r.styleSheet);else for(let r of e){let i=document.createElement("style"),n=Ge.litNonce;n!==void 0&&i.setAttribute("nonce",n),i.textContent=r.cssText,t.appendChild(i)}},It=Ye?t=>t:t=>t instanceof CSSStyleSheet?(e=>{let r="";for(let i of e.cssRules)r+=i.cssText;return Sr(r)})(t):t;var{is:Sn,defineProperty:Rn,getOwnPropertyDescriptor:Tn,getOwnPropertyNames:Cn,getOwnPropertySymbols:En,getPrototypeOf:An}=Object,Qe=globalThis,Tr=Qe.trustedTypes,Pn=Tr?Tr.emptyScript:"",In=Qe.reactiveElementPolyfillSupport,Me=(t,e)=>t,Lt={toAttribute(t,e){switch(e){case Boolean:t=t?Pn:null;break;case Object:case Array:t=t==null?t:JSON.stringify(t)}return t},fromAttribute(t,e){let r=t;switch(e){case Boolean:r=t!==null;break;case Number:r=t===null?null:Number(t);break;case Object:case Array:try{r=JSON.parse(t)}catch{r=null}}return r}},Er=(t,e)=>!Sn(t,e),Cr={attribute:!0,type:String,converter:Lt,reflect:!1,useDefault:!1,hasChanged:Er};Symbol.metadata??=Symbol("metadata"),Qe.litPropertyMetadata??=new WeakMap;var Z=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,r=Cr){if(r.state&&(r.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((r=Object.create(r)).wrapped=!0),this.elementProperties.set(e,r),!r.noAccessor){let i=Symbol(),n=this.getPropertyDescriptor(e,i,r);n!==void 0&&Rn(this.prototype,e,n)}}static getPropertyDescriptor(e,r,i){let{get:n,set:o}=Tn(this.prototype,e)??{get(){return this[r]},set(a){this[r]=a}};return{get:n,set(a){let c=n?.call(this);o?.call(this,a),this.requestUpdate(e,c,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??Cr}static _$Ei(){if(this.hasOwnProperty(Me("elementProperties")))return;let e=An(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(Me("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(Me("properties"))){let r=this.properties,i=[...Cn(r),...En(r)];for(let n of i)this.createProperty(n,r[n])}let e=this[Symbol.metadata];if(e!==null){let r=litPropertyMetadata.get(e);if(r!==void 0)for(let[i,n]of r)this.elementProperties.set(i,n)}this._$Eh=new Map;for(let[r,i]of this.elementProperties){let n=this._$Eu(r,i);n!==void 0&&this._$Eh.set(n,r)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let r=[];if(Array.isArray(e)){let i=new Set(e.flat(1/0).reverse());for(let n of i)r.unshift(It(n))}else e!==void 0&&r.push(It(e));return r}static _$Eu(e,r){let i=r.attribute;return i===!1?void 0:typeof i=="string"?i:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,r=this.constructor.elementProperties;for(let i of r.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Rr(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,r,i){this._$AK(e,i)}_$ET(e,r){let i=this.constructor.elementProperties.get(e),n=this.constructor._$Eu(e,i);if(n!==void 0&&i.reflect===!0){let o=(i.converter?.toAttribute!==void 0?i.converter:Lt).toAttribute(r,i.type);this._$Em=e,o==null?this.removeAttribute(n):this.setAttribute(n,o),this._$Em=null}}_$AK(e,r){let i=this.constructor,n=i._$Eh.get(e);if(n!==void 0&&this._$Em!==n){let o=i.getPropertyOptions(n),a=typeof o.converter=="function"?{fromAttribute:o.converter}:o.converter?.fromAttribute!==void 0?o.converter:Lt;this._$Em=n;let c=a.fromAttribute(r,o.type);this[n]=c??this._$Ej?.get(n)??c,this._$Em=null}}requestUpdate(e,r,i,n=!1,o){if(e!==void 0){let a=this.constructor;if(n===!1&&(o=this[e]),i??=a.getPropertyOptions(e),!((i.hasChanged??Er)(o,r)||i.useDefault&&i.reflect&&o===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,i))))return;this.C(e,r,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,r,{useDefault:i,reflect:n,wrapped:o},a){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??r??this[e]),o!==!0||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||i||(r=void 0),this._$AL.set(e,r)),n===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(r){Promise.reject(r)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[n,o]of this._$Ep)this[n]=o;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[n,o]of i){let{wrapped:a}=o,c=this[n];a!==!0||this._$AL.has(n)||c===void 0||this.C(n,void 0,o,c)}}let e=!1,r=this._$AL;try{e=this.shouldUpdate(r),e?(this.willUpdate(r),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(r)):this._$EM()}catch(i){throw e=!1,this._$EM(),i}e&&this._$AE(r)}willUpdate(e){}_$AE(e){this._$EO?.forEach(r=>r.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(r=>this._$ET(r,this[r])),this._$EM()}updated(e){}firstUpdated(e){}};Z.elementStyles=[],Z.shadowRootOptions={mode:"open"},Z[Me("elementProperties")]=new Map,Z[Me("finalized")]=new Map,In?.({ReactiveElement:Z}),(Qe.reactiveElementVersions??=[]).push("2.1.2");var Dt=globalThis,Ar=t=>t,Ze=Dt.trustedTypes,Pr=Ze?Ze.createPolicy("lit-html",{createHTML:t=>t}):void 0,Ot="$lit$",J=`lit$${Math.random().toFixed(9).slice(2)}$`,Nt="?"+J,Ln=`<${Nt}>`,pe=document,Oe=()=>pe.createComment(""),Ne=t=>t===null||typeof t!="object"&&typeof t!="function",Ft=Array.isArray,Nr=t=>Ft(t)||typeof t?.[Symbol.iterator]=="function",Mt=`[ 	
\f\r]`,De=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Ir=/-->/g,Lr=/>/g,de=RegExp(`>|${Mt}(?:([^\\s"'>=/]+)(${Mt}*=${Mt}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Mr=/'/g,Dr=/"/g,Fr=/^(?:script|style|textarea|title)$/i,Ht=t=>(e,...r)=>({_$litType$:t,strings:e,values:r}),l=Ht(1),_o=Ht(2),bo=Ht(3),k=Symbol.for("lit-noChange"),d=Symbol.for("lit-nothing"),Or=new WeakMap,ue=pe.createTreeWalker(pe,129);function Hr(t,e){if(!Ft(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return Pr!==void 0?Pr.createHTML(e):e}var Ur=(t,e)=>{let r=t.length-1,i=[],n,o=e===2?"<svg>":e===3?"<math>":"",a=De;for(let c=0;c<r;c++){let u=t[c],m,_,p=-1,g=0;for(;g<u.length&&(a.lastIndex=g,_=a.exec(u),_!==null);)g=a.lastIndex,a===De?_[1]==="!--"?a=Ir:_[1]!==void 0?a=Lr:_[2]!==void 0?(Fr.test(_[2])&&(n=RegExp("</"+_[2],"g")),a=de):_[3]!==void 0&&(a=de):a===de?_[0]===">"?(a=n??De,p=-1):_[1]===void 0?p=-2:(p=a.lastIndex-_[2].length,m=_[1],a=_[3]===void 0?de:_[3]==='"'?Dr:Mr):a===Dr||a===Mr?a=de:a===Ir||a===Lr?a=De:(a=de,n=void 0);let f=a===de&&t[c+1].startsWith("/>")?" ":"";o+=a===De?u+Ln:p>=0?(i.push(m),u.slice(0,p)+Ot+u.slice(p)+J+f):u+J+(p===-2?c:f)}return[Hr(t,o+(t[r]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),i]},Fe=class t{constructor({strings:e,_$litType$:r},i){let n;this.parts=[];let o=0,a=0,c=e.length-1,u=this.parts,[m,_]=Ur(e,r);if(this.el=t.createElement(m,i),ue.currentNode=this.el.content,r===2||r===3){let p=this.el.content.firstChild;p.replaceWith(...p.childNodes)}for(;(n=ue.nextNode())!==null&&u.length<c;){if(n.nodeType===1){if(n.hasAttributes())for(let p of n.getAttributeNames())if(p.endsWith(Ot)){let g=_[a++],f=n.getAttribute(p).split(J),v=/([.?@])?(.*)/.exec(g);u.push({type:1,index:o,name:v[2],strings:f,ctor:v[1]==="."?Xe:v[1]==="?"?et:v[1]==="@"?tt:me}),n.removeAttribute(p)}else p.startsWith(J)&&(u.push({type:6,index:o}),n.removeAttribute(p));if(Fr.test(n.tagName)){let p=n.textContent.split(J),g=p.length-1;if(g>0){n.textContent=Ze?Ze.emptyScript:"";for(let f=0;f<g;f++)n.append(p[f],Oe()),ue.nextNode(),u.push({type:2,index:++o});n.append(p[g],Oe())}}}else if(n.nodeType===8)if(n.data===Nt)u.push({type:2,index:o});else{let p=-1;for(;(p=n.data.indexOf(J,p+1))!==-1;)u.push({type:7,index:o}),p+=J.length-1}o++}}static createElement(e,r){let i=pe.createElement("template");return i.innerHTML=e,i}};function he(t,e,r=t,i){if(e===k)return e;let n=i!==void 0?r._$Co?.[i]:r._$Cl,o=Ne(e)?void 0:e._$litDirective$;return n?.constructor!==o&&(n?._$AO?.(!1),o===void 0?n=void 0:(n=new o(t),n._$AT(t,r,i)),i!==void 0?(r._$Co??=[])[i]=n:r._$Cl=n),n!==void 0&&(e=he(t,n._$AS(t,e.values),n,i)),e}var Je=class{constructor(e,r){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=r}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:r},parts:i}=this._$AD,n=(e?.creationScope??pe).importNode(r,!0);ue.currentNode=n;let o=ue.nextNode(),a=0,c=0,u=i[0];for(;u!==void 0;){if(a===u.index){let m;u.type===2?m=new $e(o,o.nextSibling,this,e):u.type===1?m=new u.ctor(o,u.name,u.strings,this,e):u.type===6&&(m=new rt(o,this,e)),this._$AV.push(m),u=i[++c]}a!==u?.index&&(o=ue.nextNode(),a++)}return ue.currentNode=pe,n}p(e){let r=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(e,i,r),r+=i.strings.length-2):i._$AI(e[r])),r++}},$e=class t{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,r,i,n){this.type=2,this._$AH=d,this._$AN=void 0,this._$AA=e,this._$AB=r,this._$AM=i,this.options=n,this._$Cv=n?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,r=this._$AM;return r!==void 0&&e?.nodeType===11&&(e=r.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,r=this){e=he(this,e,r),Ne(e)?e===d||e==null||e===""?(this._$AH!==d&&this._$AR(),this._$AH=d):e!==this._$AH&&e!==k&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):Nr(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==d&&Ne(this._$AH)?this._$AA.nextSibling.data=e:this.T(pe.createTextNode(e)),this._$AH=e}$(e){let{values:r,_$litType$:i}=e,n=typeof i=="number"?this._$AC(e):(i.el===void 0&&(i.el=Fe.createElement(Hr(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===n)this._$AH.p(r);else{let o=new Je(n,this),a=o.u(this.options);o.p(r),this.T(a),this._$AH=o}}_$AC(e){let r=Or.get(e.strings);return r===void 0&&Or.set(e.strings,r=new Fe(e)),r}k(e){Ft(this._$AH)||(this._$AH=[],this._$AR());let r=this._$AH,i,n=0;for(let o of e)n===r.length?r.push(i=new t(this.O(Oe()),this.O(Oe()),this,this.options)):i=r[n],i._$AI(o),n++;n<r.length&&(this._$AR(i&&i._$AB.nextSibling,n),r.length=n)}_$AR(e=this._$AA.nextSibling,r){for(this._$AP?.(!1,!0,r);e!==this._$AB;){let i=Ar(e).nextSibling;Ar(e).remove(),e=i}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},me=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,r,i,n,o){this.type=1,this._$AH=d,this._$AN=void 0,this.element=e,this.name=r,this._$AM=n,this.options=o,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=d}_$AI(e,r=this,i,n){let o=this.strings,a=!1;if(o===void 0)e=he(this,e,r,0),a=!Ne(e)||e!==this._$AH&&e!==k,a&&(this._$AH=e);else{let c=e,u,m;for(e=o[0],u=0;u<o.length-1;u++)m=he(this,c[i+u],r,u),m===k&&(m=this._$AH[u]),a||=!Ne(m)||m!==this._$AH[u],m===d?e=d:e!==d&&(e+=(m??"")+o[u+1]),this._$AH[u]=m}a&&!n&&this.j(e)}j(e){e===d?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},Xe=class extends me{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===d?void 0:e}},et=class extends me{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==d)}},tt=class extends me{constructor(e,r,i,n,o){super(e,r,i,n,o),this.type=5}_$AI(e,r=this){if((e=he(this,e,r,0)??d)===k)return;let i=this._$AH,n=e===d&&i!==d||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,o=e!==d&&(i===d||n);n&&this.element.removeEventListener(this.name,this,i),o&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},rt=class{constructor(e,r,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=r,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){he(this,e)}},Br={M:Ot,P:J,A:Nt,C:1,L:Ur,R:Je,D:Nr,V:he,I:$e,H:me,N:et,U:tt,B:Xe,F:rt},Mn=Dt.litHtmlPolyfillSupport;Mn?.(Fe,$e),(Dt.litHtmlVersions??=[]).push("3.3.3");var zr=(t,e,r)=>{let i=r?.renderBefore??e,n=i._$litPart$;if(n===void 0){let o=r?.renderBefore??null;i._$litPart$=n=new $e(e.insertBefore(Oe(),o),o,void 0,r??{})}return n._$AI(t),n};var Ut=globalThis,W=class extends Z{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let r=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=zr(r,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return k}};W._$litElement$=!0,W.finalized=!0,Ut.litElementHydrateSupport?.({LitElement:W});var Dn=Ut.litElementPolyfillSupport;Dn?.({LitElement:W});(Ut.litElementVersions??=[]).push("4.2.2");var I={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},re=t=>(...e)=>({_$litDirective$:t,values:e}),q=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,r,i){this._$Ct=e,this._$AM=r,this._$Ci=i}_$AS(e,r){return this.update(e,r)}update(e,r){return this.render(...r)}};var{I:On}=Br,jr=t=>t;var Wr=t=>t.strings===void 0,Kr=()=>document.createComment(""),ke=(t,e,r)=>{let i=t._$AA.parentNode,n=e===void 0?t._$AB:e._$AA;if(r===void 0){let o=i.insertBefore(Kr(),n),a=i.insertBefore(Kr(),n);r=new On(o,a,t,t.options)}else{let o=r._$AB.nextSibling,a=r._$AM,c=a!==t;if(c){let u;r._$AQ?.(t),r._$AM=t,r._$AP!==void 0&&(u=t._$AU)!==a._$AU&&r._$AP(u)}if(o!==n||c){let u=r._$AA;for(;u!==o;){let m=jr(u).nextSibling;jr(i).insertBefore(u,n),u=m}}}return r},ie=(t,e,r=t)=>(t._$AI(e,r),t),Nn={},it=(t,e=Nn)=>t._$AH=e,qr=t=>t._$AH,nt=t=>{t._$AR(),t._$AA.remove()};var Vr=(t,e,r)=>{let i=new Map;for(let n=e;n<=r;n++)i.set(t[n],n);return i},X=re(class extends q{constructor(t){if(super(t),t.type!==I.CHILD)throw Error("repeat() can only be used in text expressions")}dt(t,e,r){let i;r===void 0?r=e:e!==void 0&&(i=e);let n=[],o=[],a=0;for(let c of t)n[a]=i?i(c,a):a,o[a]=r(c,a),a++;return{values:o,keys:n}}render(t,e,r){return this.dt(t,e,r).values}update(t,[e,r,i]){let n=qr(t),{values:o,keys:a}=this.dt(e,r,i);if(!Array.isArray(n))return this.ut=a,o;let c=this.ut??=[],u=[],m,_,p=0,g=n.length-1,f=0,v=o.length-1;for(;p<=g&&f<=v;)if(n[p]===null)p++;else if(n[g]===null)g--;else if(c[p]===a[f])u[f]=ie(n[p],o[f]),p++,f++;else if(c[g]===a[v])u[v]=ie(n[g],o[v]),g--,v--;else if(c[p]===a[v])u[v]=ie(n[p],o[v]),ke(t,u[v+1],n[p]),p++,v--;else if(c[g]===a[f])u[f]=ie(n[g],o[f]),ke(t,n[p],n[g]),g--,f++;else if(m===void 0&&(m=Vr(a,f,v),_=Vr(c,p,g)),m.has(c[p]))if(m.has(c[g])){let T=_.get(a[f]),S=T!==void 0?n[T]:null;if(S===null){let w=ke(t,n[p]);ie(w,o[f]),u[f]=w}else u[f]=ie(S,o[f]),ke(t,n[p],S),n[T]=null;f++}else nt(n[g]),g--;else nt(n[p]),p++;for(;f<=v;){let T=ke(t,u[v+1]);ie(T,o[f]),u[f++]=T}for(;p<=g;){let T=n[p++];T!==null&&nt(T)}return this.ut=a,it(t,u),k}});var Gr="important",Fn=" !"+Gr,N=re(class extends q{constructor(t){if(super(t),t.type!==I.ATTRIBUTE||t.name!=="style"||t.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(t){return Object.keys(t).reduce((e,r)=>{let i=t[r];return i==null?e:e+`${r=r.includes("-")?r:r.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${i};`},"")}update(t,[e]){let{style:r}=t.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(e)),this.render(e);for(let i of this.ft)e[i]==null&&(this.ft.delete(i),i.includes("-")?r.removeProperty(i):r[i]=null);for(let i in e){let n=e[i];if(n!=null){this.ft.add(i);let o=typeof n=="string"&&n.endsWith(Fn);i.includes("-")||o?r.setProperty(i,o?n.slice(0,-11):n,o?Gr:""):r[i]=n}}return k}});var L=re(class extends q{constructor(t){if(super(t),t.type!==I.PROPERTY&&t.type!==I.ATTRIBUTE&&t.type!==I.BOOLEAN_ATTRIBUTE)throw Error("The `live` directive is not allowed on child or event bindings");if(!Wr(t))throw Error("`live` bindings can only contain a single expression")}render(t){return t}update(t,[e]){if(e===k||e===d)return e;let r=t.element,i=t.name;if(t.type===I.PROPERTY){if(e===r[i])return k}else if(t.type===I.BOOLEAN_ATTRIBUTE){if(!!e===r.hasAttribute(i))return k}else if(t.type===I.ATTRIBUTE&&r.getAttribute(i)===e+"")return k;return it(t),e}});var Yr="parcels";function ne(t,e,r){return t.callService(Yr,e,r,void 0,!1)}function V(t,e,r={}){return t.callWS({...r,type:`${Yr}/${e}`})}var se={amazon:"Amazon Logistics",asendia:"Asendia",bpost:"bpost",brt:"BRT",cainiao:"Cainiao",chronopost:"Chronopost",colissimo:"Colissimo",correos:"Correos",correos_express:"Correos Express",ctt:"CTT",ctt_expresso:"CTT Expresso",deutsche_post:"Deutsche Post",dhl:"DHL",dpd:"DPD",evri:"Evri",fedex:"FedEx",gls:"GLS",hermes:"Hermes",inpost:"InPost",la_poste:"La Poste",mondial_relay:"Mondial Relay",mrw:"MRW",nacex:"Nacex",paack:"Paack",postnl:"PostNL",poste_italiane:"Poste Italiane",royal_mail:"Royal Mail",sda:"SDA",seur:"SEUR",tnt:"TNT",ups:"UPS",usps:"USPS",vinted_go:"Vinted Go",yunexpress:"YunExpress",other:"Other"};function st(){return Object.entries(se).filter(([t])=>t!=="other").map(([t,e])=>({id:t,name:e})).sort((t,e)=>t.name.localeCompare(e.name,"en",{sensitivity:"base"})).concat([{id:"other",name:se.other??"Other"}])}function Qr(t){return Object.hasOwn(se,t)?se[t]??t:t}var s={weekCardName:"Parcels week",weekCardDescription:"A Monday to Sunday calendar of your parcel deliveries.",listCardName:"Parcels without a date",listCardDescription:"Active parcels that don't have a delivery date yet.",reviewCardName:"Parcels review",reviewCardDescription:"E-mails that need a decision before Parcels uses them. Only shown to administrators.",defaultWeekTitle:"Parcels",defaultListTitle:"No date yet",defaultReviewTitle:"Parcels review",loading:"Loading parcels\u2026",loadError:"Couldn't load parcels: {message}",refreshError:"Couldn't update parcels: {message}",unknownError:"Unknown error",close:"Close",cancel:"Cancel",save:"Save",dismissMessage:"Dismiss message",configInvalid:"Invalid configuration: expected a map of options.",configTitle:'Invalid configuration: "title" must be text.',configShowArchived:'Invalid configuration: "show_archived" must be true or false.',previousWeek:"Previous week",nextWeek:"Next week",today:"Today",goToToday:"Go to the current week",weekNavigation:"Week navigation",weekOf:"Week of {range}",refresh:"Check mailboxes now",refreshFailed:"Couldn't check the mailboxes: {message}",addParcel:"Add parcel",noDeliveriesThisWeek:"No deliveries this week",noDeliveriesThisDay:"No deliveries",filterLabel:"Show parcels",filterAll:"All",filterActive:"Active",filterRecent:"Recent",filterRecentHint:"Changed or expected this week",filterCompleted:"Completed",filterEmptyWeek:"Nothing to show this week with this filter",filterNote:"Filter: {filter}",filterShowAll:"Show all",todayTag:"Today",privateParcel:"Private parcel",unnamedParcel:"Parcel",packages:"{count} packages",carrierNotKnown:"Carrier not known yet",carrierNotKnownLabel:"carrier not known yet",carrierIs:"carrier {carrier}",hasCode:"PIN in the details",pin:"PIN {code}",unknownSeller:"Unknown seller",itemsCount:"{count} items",itemsNotKnown:"Items not known yet",possibly:"Possibly: {items}",possiblyOr:" or ",itemsMore:"{name} +{count}",possibleMatches:"Possibly the same package as",possibleMatchesHint:"Not confirmed: this package's e-mails don't name the order. Merge the parcel it is, or rule one out.",notThisOne:"Not this one",notThisOneLabel:"{candidate} isn't {title}",aiBadge:"AI",aiBadgeLabel:"found by the local AI",aiFilledLabel:"details filled in by the local AI",privateLabel:"private",autoMerged:"Auto-merged \u2014 check",autoMergedLabel:"merged automatically, please check",undo:"Undo",undoMergeLabel:"Undo the automatic merge of {title}",undoFailed:"Couldn't undo the merge: {message}",keep:"Keep",keepMergeLabel:"Keep the automatic merge of {title}",keepFailed:"Couldn't keep the merge: {message}",inferred:"Delivery inferred \u2014 check",inferredLabel:"delivery inferred, please check",undoInferredLabel:"Undo the inferred delivery of {title}",undoInferredFailed:"Couldn't undo the delivery: {message}",keepInferredLabel:"Keep the inferred delivery of {title}",keepInferredFailed:"Couldn't keep the delivery: {message}",continuesBefore:"started before this week",continuesAfter:"continues after this week",deliveredOn:"delivered {date}",returnedOn:"returned {date}",expectedOn:"expected {date}",readyForPickupSince:"ready for pickup since {date}",statusOn:"{status} on {date}",windowFrom:"from {time}",windowUntil:"until {time}",noUndatedParcels:"Every active parcel has a delivery date.",noUndatedMatch:"No parcels without a date match this filter.",tabReview:"Needs review",tabFiltered:"Filtered",tabCount:"{label} ({count})",possibleDuplicate:"Possible duplicate",suggestionTitle:"Same parcel as {parcel}?",suggestionHint:"Merge the parcel that is the same one, or keep them apart.",reasonIs:"Reason: {reason}",mergeSuggested:"Merge",mergeSuggestedLabel:"Merge {candidate} into {title}",keepApart:"Keep apart",keepApartLabel:"Keep {title} apart from these parcels",reviewTabs:"Review lists",emptyReview:"Nothing to review.",emptyFiltered:"No filtered e-mails.",filteredHint:"E-mails the local AI classed as not about a parcel.",receivedOn:"Received {date}",noSubject:"(no subject)",mailboxOf:"Mailbox: {owner}",unverifiedSender:"Unverified sender",unverifiedSenderHint:"This e-mail didn't pass the sender checks (DKIM/DMARC). Make sure it's genuine before you accept it.",aiSuggestionLabel:"read by the local AI",suggestion:"Suggestion",noSuggestion:"No suggestion. Use Edit to enter the details yourself.",accept:"Accept",acceptWithChanges:"Accept with changes",edit:"Edit",dismiss:"Dismiss",trustSender:"Trust this sender",trustSenderHint:"Treat e-mails from {domain} as a known sender from now on",trustQuestion:"Trust {domain}? This e-mail failed the sender checks, and anyone can send e-mail that claims to come from {domain}. Its e-mails waiting here will be added as they are.",trustConfirm:"Trust {domain}",trustedSenderNote:"You trust {domain}, but this e-mail failed the sender checks. Make sure it's genuine before you accept it.",trustDone:"Trusted {domain}.",trustDoneWith:"Trusted {domain}: {parts}.",trustAddedOne:"added 1 e-mail",trustAddedMany:"added {count} e-mails",trustRecheckOne:"reading 1 e-mail again",trustRecheckMany:"reading {count} e-mails again",trustKeptOne:"1 still needs review",trustKeptMany:"{count} still need review",senderChecks:"Sender check details",failedChecks:"Checks the AI answer failed",checkHeaders:"Authentication headers",checkServers:"Servers, in order",checkNoServer:"(no name)",checkOriginals:"Renamed by the mail provider",checkUsed:"Header used",checkUsedNone:"None",checkUsedHeader:"Header {n}",checkNoResult:"none",ignoreSender:"Ignore this sender",ignoreSenderHint:"Skip e-mails from {domain} from now on",restore:"Restore",clear:"Clear",clearHint:"Remove this e-mail from the list. It won't be read again.",clearAll:"Clear all",clearAllQuestion:"Clear all filtered e-mails? They won't be read again.",aiQueueOne:"1 e-mail waiting for the local AI",aiQueueMany:"{count} e-mails waiting for the local AI",aiQueueMinutes:"{queue}, about {minutes} min",aiQueueHours:"{queue}, about {hours} h",fieldKind:"Type",fieldMerchant:"Merchant",fieldCarrier:"Carrier",fieldTrackingNumber:"Tracking number",fieldTrackingNumbers:"Tracking numbers",fieldOrderNumbers:"Order numbers",fieldReference:"Shipment reference",fieldEtaStart:"Expected from",fieldEtaEnd:"Expected until",fieldWindowStart:"Time window from",fieldWindowEnd:"Time window until",fieldPickupPoint:"Pickup point",fieldPickupCode:"PIN or pickup code",fieldItems:"Items",fieldPrivate:"Private (only the owners can see it)",hintList:"Separate with commas or new lines.",hintItems:"One per line.",carrierAuto:"Detect automatically",carrierUnknown:"Unknown",details:"Parcel details",status:"Status",sinceDate:"since {date}",dateNotKnown:"Date not known",dateNotKnownInline:"date not known",carrier:"Delivered by",notKnownYet:"Not known yet",trackOnline:"Track on the carrier's site",opensInNewTab:"(opens in a new tab)",trackingNumber:"Tracking number",copy:"Copy",copyTrackingNumber:"Copy the tracking number",copied:"Copied.",copyFailed:"Couldn't copy automatically. The number is selected, so you can copy it yourself.",merchant:"Merchant",seller:"Sold by",parcelAppName:"Name in the Parcel app",orders:"Orders",references:"Shipment reference",items:"Items",expected:"Expected",timeWindow:"Time window",pickupPoint:"Pickup point",pickupCode:"PIN or pickup code",packagesInShipment:"Packages",showPackage:"Show package {name}",showParcel:"Show parcel {name}",parcelId:"Parcel ID",delivered:"Delivered",timeline:"Timeline",noTimeline:"No events yet.",provisional:"Provisional",provisionalHint:"Made from an order e-mail. It's completed when the shipping e-mail arrives.",archived:"Archived",private:"Private",loadingDetails:"Loading details\u2026",detailsError:"Couldn't load the details: {message}",retry:"Try again",notFound:"This parcel no longer exists.",aiNotice:"Found by the local AI. Check the details, then confirm them.",aiFilledNotice:"Some details were filled in by the local AI. Check them, then confirm.",confirm:"Confirm",confirmLabel:"Confirm the details the local AI found",confirmFilledLabel:"Confirm the details the local AI filled in",mergedNotice:"Merged automatically ({reason}). Check that it's one parcel.",mergedNoticeNoReason:"Merged automatically. Check that it's one parcel.",inferredNotice:"Probably delivered: another parcel from this shop was delivered around the expected day. Undo if it hasn't arrived.",inferredQuietNotice:"Probably delivered: no news for three weeks. Undo if it hasn't arrived.",markDelivered:"Mark delivered",editDate:"Edit date",checkAgain:"Check again",checkingAgain:"Checking\u2026",checkAgainHint:"Read this parcel's e-mails again, and let the local AI look for what's missing",checkAgainReadOne:"Read 1 e-mail again.",checkAgainReadMany:"Read {count} e-mails again.",checkAgainGoneOne:"1 e-mail is no longer in the mailbox.",checkAgainGoneMany:"{count} e-mails are no longer in the mailbox.",checkAgainFailedOne:"1 e-mail couldn't be downloaded; try again later.",checkAgainFailedMany:"{count} e-mails couldn't be downloaded; try again later.",checkAgainNoEmails:"This parcel has no e-mails to read again.",checkAgainQueuedOne:"The local AI is checking 1 e-mail.",checkAgainQueuedMany:"The local AI is checking {count} e-mails.",checkAgainSuggest:"What it finds waits under Needs review.",checkAgainAuto:"What it finds is added to this parcel.",checkAgainNothingForAi:"There was nothing for the local AI to fill in.",checkAgainAiOff:"The local AI is off.",mergeWith:"Merge with\u2026",split:"Split\u2026",archive:"Archive",actions:"Actions",mergeIntro:"Choose the parcel to merge into this one. Likely matches come first.",mergeChoose:"Parcel",mergeConfirm:"Merge",mergeChooseFirst:"Choose a parcel first.",mergeSearch:"Search",mergeSearchPlaceholder:"Shop, item, order, number or carrier",mergeShowOlder:"Show older ({count})",mergeNoMatch:"No parcel matches the search.",noMergeCandidates:"There are no other parcels to merge with.",numberTail:"No. {tail}",orderTail:"Order {tail}",splitIntro:"Choose what to move to a new parcel.",splitConfirm:"Split off",splitHint:"Choose at least one, but not all of them.",archiveQuestion:"Archive this parcel? It no longer counts as active.",dateEndBeforeStart:"The end date is before the start date.",dateEndWithoutStart:"Set a start date too.",windowEndBeforeStart:"The time window must end after it starts.",actionFailed:"That didn't work: {message}",addTitle:"Add parcel",addSubmit:"Add",trackingRequired:"Enter a tracking number.",returnBadge:"Return",privateReturn:"Private return",returnTo:"Return to {merchant}",returnPlain:"Return",returnPickup:"Return pickup",returnPickedUp:"Return picked up",returnReceived:"Received by the shop",returnStarted:"Return started",pickupOn:"pickup {date}",pickedUpOn:"picked up {date}",returnStartedOn:"started {date}",receivedByShopLabel:"received by the shop",pickupRuleEmail:"date from the e-mail",pickupRuleNextWorkingDay:"the e-mail says the next working day",pickupRuleAssumed:"usually the working day after the e-mail",returnDetails:"Return details",pickup:"Pickup",returnStartedDay:"Started",returnCarrier:"Carrier",returnSentBackFrom:"Original delivery",returnEmails:"E-mails",returnNotFound:"This return no longer exists.",returnHint:"Items you send back to a shop. Their parcel keeps its delivery; the return shows on its pickup day.",removeReturn:"Remove",removeReturnQuestion:"Remove this return? Its e-mails won't be read again, and a delivery worked out only from it is undone.",inferredReturnNotice:"Probably delivered: you're sending its items back. Undo if it hasn't arrived."},Zr={ordered:"Ordered",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",exception:"Problem with delivery",ready_for_pickup:"Ready for pickup",returned:"Returned to sender",cancelled:"Cancelled"},ot={order:"Order confirmation",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",ready_for_pickup:"Ready for pickup",delayed:"Delayed",customs:"Held at customs",return:"Returned to sender",customer_return:"Return pickup",cancelled:"Cancelled",code:"Delivery code",not_parcel:"Not about a parcel",unknown:"Unknown"},Jr={parser:"E-mail",ai:"Local AI",manual:"Added by hand",seventeentrack:"17TRACK",parcelapp:"Parcel app",inferred:"Inferred from another delivery",inferred_return:"Inferred from a return",quiet:"No news for three weeks"},Xr={unknown_sender:"Unknown sender",not_aligned:"The sender's domain isn't authenticated (DKIM/DMARC)",no_auth_header:"No authentication results in the e-mail",untrusted_authserv:"Authentication results from an unknown server",multiple_auth_results:"More than one set of authentication results, so it can't tell which is real",low_confidence:"Not sure about the details",unknown_format:"Unknown e-mail format",ai_suggestion:"Read by the local AI",ai_fill:"The local AI found details the parser missed",ai_unavailable:"The local AI wasn't available",ai_timeout:"The local AI took too long on this e-mail",ai_rejected:"The local AI's answer didn't pass the checks",restored:"Moved back from Filtered"},ei={same_number:"same tracking number",same_merchant_eta:"same shop and delivery date",same_merchant_day:"same shop, delivered on the expected day",same_merchant_domain:"the shop's tracked shipment followed its order",same_order:"same order",same_reference:"same shipment reference"};function h(t,e){return t.replace(/\{(\w+)\}/g,(r,i)=>Object.hasOwn(e,i)?String(e[i]):r)}function B(t){if(typeof t=="string"&&t.trim())return t;if(t&&typeof t=="object"){let e=t.message;if(typeof e=="string"&&e.trim())return e;let r=t.code;if(typeof r=="string"&&r.trim())return r}return s.unknownError}var Hn=["a[href]","button:not([disabled])","input:not([disabled]):not([type='hidden'])","select:not([disabled])","textarea:not([disabled])","[tabindex]:not([tabindex='-1'])"].join(",");function Un(t){return[...t.querySelectorAll(Hn)].filter(e=>!e.closest("[hidden], [inert]")&&e.getClientRects().length>0)}function ti(t,e){if(t.key!=="Tab"||t.altKey||t.ctrlKey||t.metaKey)return;let r=Un(e),i=r[0],n=r[r.length-1];if(!i||!n){t.preventDefault(),e.focus();return}let a=e.getRootNode().activeElement,c=a instanceof HTMLElement&&e.contains(a)&&a!==e;t.shiftKey&&(!c||a===i)?(t.preventDefault(),n.focus()):!t.shiftKey&&(!c||a===n)&&(t.preventDefault(),i.focus())}var Bn="parcels-error",ri="parcels-open-parcel",ii="parcels-open-return",oe=class extends W{static properties={hass:{attribute:!1},_open:{state:!0},_busy:{state:!0},_error:{state:!0}};_returnFocus=null;_pressedBackdrop=!1;_hadFocus=!1;_session=0;constructor(){super(),this.hass=void 0,this._open=!1,this._busy=!1,this._error=null}render(){return l`<dialog
      aria-labelledby="dialog-title"
      @close=${this._onClose}
      @keydown=${this._onKeyDown}
      @pointerdown=${this._onPointerDown}
      @click=${this._onClick}
    >
      ${this._open?this.renderContent():d}
    </dialog>`}renderContent(){return d}canLightDismiss(){return!this._busy}dialogClosed(){}get isOpen(){return this._open}async showDialog(e){this._session+=1,this._returnFocus=e,this._open=!0,this._busy=!1,this._error=null,await this.updateComplete;let r=this._dialog();!r||!this._open||!this.isConnected||(r.open||r.showModal(),this.focusInDialog("[data-autofocus]"))}closeDialog(){let e=this._dialog();e?.open&&e.close(),this._finishClose(!0)}focusInDialog(e){this.renderRoot.querySelector(`dialog ${e}`)?.focus()}async focusAfterRender(e){await this.updateComplete,this._open&&this.focusInDialog(e)}async runAction(e,r){if(this._busy)return;let i=this._session;this._busy=!0,this._error=null;try{await e(),this._open&&this._session===i&&r?.()}catch(n){let o=h(s.actionFailed,{message:B(n)});this._open&&this._session===i?this._error=o:this.dispatchEvent(new CustomEvent(Bn,{detail:o}))}finally{this._session===i&&(this._busy=!1)}}disconnectedCallback(){super.disconnectedCallback(),this._finishClose(!1)}willUpdate(e){this._hadFocus=this._open&&!!this.shadowRoot?.activeElement}updated(e){this._hadFocus&&this._open&&!this.shadowRoot?.activeElement&&this.focusInDialog("[data-autofocus]"),this._hadFocus=!1}_dialog(){return this.renderRoot.querySelector("dialog")}_finishClose(e){if(!this._open)return;let r=this._returnFocus;this._returnFocus=null,this._open=!1,this._busy=!1,this._error=null,this._pressedBackdrop=!1,this.dialogClosed(),e&&r?.()}_onClose(e){let r=e.currentTarget;e.target===r&&!r.open&&this._finishClose(!0)}_onKeyDown(e){ti(e,e.currentTarget)}_onPointerDown(e){this._pressedBackdrop=e.target===e.currentTarget}_onClick(e){let r=this._pressedBackdrop&&e.target===e.currentTarget;this._pressedBackdrop=!1,r&&this.canLightDismiss()&&this.closeDialog()}};var zn=/^(\d{4})-(\d{2})-(\d{2})$/,jn=/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)(?:[.,](\d+))?(Z|[+-]\d{2}(?::?\d{2})?)?$/i,Kn=[31,28,31,30,31,30,31,31,30,31,30,31];function Wn(t){return t%4===0&&t%100!==0||t%400===0}function qn(t,e){return e===2&&Wn(t)?29:Kn[e-1]??0}function ct(t){if(typeof t!="string")return null;let e=zn.exec(t);if(!e)return null;let r=Number(e[1]),i=Number(e[2]),n=Number(e[3]);return i<1||i>12||n<1||n>qn(r,i)?null:{year:r,month:i,day:n}}function z(t){return ct(t)!==null}function at(t){let e=ct(t);if(!e)throw new RangeError(`Not a YYYY-MM-DD date: ${t}`);return e}function lt({year:t,month:e,day:r}){let i=e<=2?t-1:t,n=Math.floor(i/400),o=i-n*400,a=(e+9)%12,c=Math.floor((153*a+2)/5)+r-1,u=o*365+Math.floor(o/4)-Math.floor(o/100)+c;return n*146097+u-719468}function Vn(t){let e=t+719468,r=Math.floor(e/146097),i=e-r*146097,n=Math.floor((i-Math.floor(i/1460)+Math.floor(i/36524)-Math.floor(i/146096))/365),o=i-(365*n+Math.floor(n/4)-Math.floor(n/100)),a=Math.floor((5*o+2)/153),c=o-Math.floor((153*a+2)/5)+1,u=a<10?a+3:a-9;return{year:n+r*400+(u<=2?1:0),month:u,day:c}}function Gn({year:t,month:e,day:r}){return`${String(t).padStart(4,"0")}-${String(e).padStart(2,"0")}-${String(r).padStart(2,"0")}`}function ee(t,e){return Gn(Vn(lt(at(t))+e))}function ae(t,e){return lt(at(e))-lt(at(t))}function Yn(t){return((lt(at(t))+3)%7+7)%7}function He(t){return ee(t,-Yn(t))}function si(t){return Array.from({length:7},(e,r)=>ee(t,r))}function $(t,e){return t<e?-1:t>e?1:0}function oi(t,e){return $(t,e)>=0?t:e}function G(t){if(typeof t!="string")return null;let e=jn.exec(t.trim());if(!e)return null;let[,r,i,n,o]=e;if(!r||!i||!z(r))return null;let a=n?`.${n.slice(0,3).padEnd(3,"0")}`:"",c="Z";if(o&&o.toUpperCase()!=="Z"){let m=o.slice(1).replace(":","").padEnd(4,"0");c=`${o[0]}${m.slice(0,2)}:${m.slice(2,4)}`}let u=Date.parse(`${r}T${i}${a}${c}`);return Number.isNaN(u)?null:u}var ni=new Map;function Qn(t){let e=ni.get(t);if(!e){let r={calendar:"gregory",numberingSystem:"latn",year:"numeric",month:"2-digit",day:"2-digit"};try{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:t})}catch{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:"UTC"})}ni.set(t,e)}return e}function M(t,e){if(z(t))return t;let r=G(t);if(r===null)return null;let i="",n="",o="";for(let c of Qn(e).formatToParts(r))c.type==="year"?i=c.value:c.type==="month"?n=c.value:c.type==="day"&&(o=c.value);let a=`${i.padStart(4,"0")}-${n}-${o}`;return z(a)?a:null}function Zn(t){return[...new Set(t)]}function ai(t){return Zn(t.split(/[\n,;]+/).map(e=>e.trim()).filter(Boolean))}function Jn(t){return t.split(/\r?\n/).map(e=>e.trim()).filter(Boolean)}function Y(t){let e=/^(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?$/.exec((t??"").trim());if(!e)return null;let r=Number(e[1]),i=Number(e[2]);return r>23||i>59?null:`${String(r).padStart(2,"0")}:${String(i).padStart(2,"0")}`}function j(t){let e=t.trim();return e||null}function Xn(t,e){return e&&!t?s.dateEndWithoutStart:t&&e&&$(e,t)<0?s.dateEndBeforeStart:null}function es(t,e){let r=Y(t),i=Y(e);return r&&i&&i<=r?s.windowEndBeforeStart:null}function li(t){return{eta_start:t.eta_start??"",eta_end:t.eta_end??"",window_start:Y(t.window_start)??"",window_end:Y(t.window_end)??""}}function dt(t){let e=Xn(t.eta_start,t.eta_end);if(e)return{message:e,field:e===s.dateEndWithoutStart?"eta_start":"eta_end"};let r=es(t.window_start,t.window_end);return r?{message:r,field:"window_end"}:null}function ci(t,e){return{parcel_id:t,eta_start:j(e.eta_start),eta_end:j(e.eta_end),window_start:Y(e.window_start),window_end:Y(e.window_end)}}var di="shipped";function Bt(t){return{kind:t?.kind||di,merchant:t?.merchant??"",carrier:t?.carrier??"",tracking_numbers:(t?.tracking_numbers??[]).join(", "),order_numbers:(t?.order_numbers??[]).join(", "),eta_start:t?.eta_start??"",eta_end:t?.eta_end??"",window_start:Y(t?.window_start)??"",window_end:Y(t?.window_end)??"",pickup_point:t?.pickup_point??"",pickup_code:t?.pickup_code??"",items:(t?.items??[]).join(`
`),reference:t?.reference??""}}function ui(t){return{kind:t.kind.trim()||di,merchant:j(t.merchant),carrier:j(t.carrier),tracking_numbers:ai(t.tracking_numbers),order_numbers:ai(t.order_numbers),eta_start:j(t.eta_start),eta_end:j(t.eta_end),window_start:Y(t.window_start),window_end:Y(t.window_end),pickup_point:j(t.pickup_point),pickup_code:j(t.pickup_code),items:Jn(t.items),reference:j(t.reference)}}function pi(t){let e=t.tracking_number.trim();if(!e)return null;let r={tracking_number:e},i=j(t.carrier);i&&(r.carrier=i);let n=j(t.merchant);return n&&(r.merchant=n),t.private&&(r.private=!0),r}function zt(t,e){return t.length>0&&t.length<e}var ts="https://github.com/fratei/ha-parcels";function F(t,e){customElements.get(t)||customElements.define(t,e)}function we(t,e,r){let i=window;Array.isArray(i.customCards)||(i.customCards=[]);let n=i.customCards;n.some(o=>o?.type===t)||n.push({type:t,name:e,description:r,preview:!0,documentationURL:ts})}var H=x`
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
`,ut=x`
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
`,xe=x`
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
`;var hi={tracking_number:"",carrier:"",merchant:"",private:!1},jt=class extends oe{static properties={_form:{state:!0},_missingNumber:{state:!0}};static styles=[H,xe,x`
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
    `];constructor(){super(),this._form=hi,this._missingNumber=!1}async open(e=null){this._form=hi,this._missingNumber=!1,await this.showDialog(e)}canLightDismiss(){return!1}renderContent(){let e=this._form,r=this._missingNumber;return l`
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
              .value=${L(e.tracking_number)}
              aria-invalid=${r?"true":"false"}
              aria-describedby=${r?"tracking-error":d}
              @input=${this._onInput}
            />
          </label>
          ${r?l`<p class="field-error" id="tracking-error">${s.trackingRequired}</p>`:d}
          <label class="field">
            <span class="field-label">${s.fieldCarrier}</span>
            <select name="carrier" @change=${this._onInput}>
              <option value="" ?selected=${e.carrier===""}>${s.carrierAuto}</option>
              ${st().map(i=>l`<option value=${i.id} ?selected=${e.carrier===i.id}>
                    ${i.name}
                  </option>`)}
            </select>
          </label>
          <label class="field">
            <span class="field-label">${s.fieldMerchant}</span>
            <input
              name="merchant"
              autocomplete="off"
              .value=${L(e.merchant)}
              @input=${this._onInput}
            />
          </label>
          <label class="check-row">
            <input
              type="checkbox"
              name="private"
              .checked=${L(e.private)}
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
          </div>`:d}
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
    `}_onInput(e){let r=e.currentTarget,i=r.name,n=r instanceof HTMLInputElement&&r.type==="checkbox"?r.checked:r.value;this._form={...this._form,[i]:n},i==="tracking_number"&&this._missingNumber&&r.value.trim()&&(this._missingNumber=!1)}_submit(e){e.preventDefault();let r=this.hass;if(!r||this._busy)return;let i=pi(this._form);if(!i){this._missingNumber=!0,this.focusAfterRender("#tracking-number");return}this.runAction(()=>ne(r,"add",i),()=>this.closeDialog())}};F("parcels-add-dialog",jt);var fe=re(class extends q{constructor(t){if(super(t),t.type!==I.ATTRIBUTE||t.name!=="class"||t.strings?.length>2)throw Error("`classMap()` can only be used in the `class` attribute and must be the only part in the attribute.")}render(t){return" "+Object.keys(t).filter(e=>t[e]).join(" ")+" "}update(t,[e]){if(this.st===void 0){this.st=new Set,t.strings!==void 0&&(this.nt=new Set(t.strings.join(" ").split(/\s/).filter(i=>i!=="")));for(let i in e)e[i]&&!this.nt?.has(i)&&this.st.add(i);return this.render(e)}let r=t.element.classList;for(let i of this.st)i in e||(r.remove(i),this.st.delete(i));for(let i in e){let n=!!e[i];n===this.st.has(i)||this.nt?.has(i)||(n?(r.add(i),this.st.add(i)):(r.remove(i),this.st.delete(i)))}return k}});function rs(t){try{return Intl.DateTimeFormat.supportedLocalesOf([t]),t}catch{return"en"}}function is(){let t=new Intl.DateTimeFormat(void 0,{hour:"numeric"}).resolvedOptions().hourCycle;return t==="h11"||t==="h12"}function Se(t,e){let r=rs(t?.locale?.language||t?.language||"en"),i=t?.locale?.time_format,n;i==="12"?n=!0:i==="24"?n=!1:i==="system"&&(n=is());let o=t?.locale?.time_zone==="local"?void 0:e||t?.config?.time_zone||void 0;return{language:r,hour12:n,timeZone:o}}var mi=new Map;function Ue(t,e,r){let i=e.hour!==void 0||e.timeStyle!==void 0,n={...e,timeZone:r?"UTC":t.timeZone};i&&t.hour12!==void 0&&(n.hour12=t.hour12);let o=JSON.stringify([t.language,n]),a=mi.get(o);if(!a){try{a=new Intl.DateTimeFormat(t.language,n)}catch{a=new Intl.DateTimeFormat(t.language,{...n,timeZone:void 0})}mi.set(o,a)}return a}function Kt(t){let e=ct(t);return e?new Date(Date.UTC(e.year,e.month-1,e.day)):null}var fi={weekday:"short",day:"numeric",month:"short"},gi={day:"numeric",month:"short",year:"numeric"};function D(t,e,r=fi){let i=Kt(t);return i?Ue(e,r,!0).format(i):t}function U(t,e,r,i=fi){let n=Kt(t),o=Kt(e);return!n||!o?[t,e].filter(Boolean).join(" \u2013 "):t===e?Ue(r,i,!0).format(n):Ue(r,i,!0).formatRange(n,o)}function pt(t,e){let r=/^(\d{1,2}):(\d{2})/.exec(t);if(!r)return t;let i=new Date(Date.UTC(1970,0,1,Number(r[1]),Number(r[2])));return Ue(e,{hour:"numeric",minute:"2-digit"},!0).format(i)}function Re(t,e,r){return t&&e?`${pt(t,r)}\u2013${pt(e,r)}`:t?h(s.windowFrom,{time:pt(t,r)}):e?h(s.windowUntil,{time:pt(e,r)}):null}function A(t,e){if(!t)return"";let r=G(t);return r===null?t:Ue(e,{dateStyle:"medium",timeStyle:"short"},!1).format(r)}function ge(t){if(typeof t!="string")return null;let e=t.trim();return e||null}function _i(t){let e=t.trim();if(!/^[a-z0-9]+(?:[_-][a-z0-9]+)*$/.test(e))return e;let r=e.replace(/[_-]+/g," ");return r.charAt(0).toUpperCase()+r.slice(1)}function Be(t,e){let r=ge(e);return r?Object.hasOwn(t,r)?t[r]??r:_i(r):""}function R(t){let e=ge(t.carrier_name);if(e)return e;let r=ge(t.carrier);return!r||r==="other"?null:Object.hasOwn(se,r)?Qr(r):_i(r)}function P(t){return t.restricted?s.privateParcel:ge(t.merchant)??ge(t.name)??R(t)??ge(t.tracking_number)??s.unnamedParcel}function bi(t){let e=ge(t.name);return e&&!t.restricted&&e!==P(t)?e:null}function vi(t){return t.eta_source==="parcelapp"?Te(t.eta_source):null}function K(t){return Be(Zr,t)}function Wt(t){return Be(ot,t)}function Te(t){return Be(Jr,t)}function yi(t){switch(t.inferred_reason){case"quiet":return s.inferredQuietNotice;case"return":return s.inferredReturnNotice;default:return s.inferredNotice}}function $i(t){return Be(Xr,t)}function ht(t){return Be(ei,t)}var mt="var(--secondary-text-color, #727272)",ki="var(--info-color, #039be5)",ns="var(--warning-color, #ffa600)",ss="var(--success-color, #43a047)",wi="var(--error-color, #db4437)",os="var(--purple-color, #926bc7)",xi={ordered:mt,shipped:ki,in_transit:ki,out_for_delivery:ns,delivered:ss,attempted:wi,exception:wi,ready_for_pickup:os,returned:mt,cancelled:mt};function ze(t){return Object.hasOwn(xi,t)?xi[t]:mt}var as=new Set(["delivered","returned","cancelled"]);function _e(t){return!as.has(t)}function C(t){let e=z(t.eta_start)?t.eta_start:null,r=z(t.eta_end)?t.eta_end:null,i=e??r;return i?{start:i,end:r&&$(r,i)>=0?r:i}:null}function le(t){return _e(t.status)}function qt(t,e){let r=G(t.status_time),i=G(e.status_time);return r!==i?r===null?1:i===null?-1:i-r:t.id<e.id?-1:t.id>e.id?1:0}function Ei(t){return t.filter(e=>le(e)&&!e.archived&&C(e)===null).sort(qt)}var ls=7,cs=9999;function Si(t){return t.replace(/[^0-9a-z]/gi,"").toUpperCase()}function Ri(t){return t.merchant?.trim().toLowerCase()??""}function Ti(t,e){let r=C(t);if(r)return r;let i=M(t.delivered_at??t.status_time,e);return i?{start:i,end:i}:null}function Ci(t,e,r){let i=Ti(t,r),n=Ti(e,r);return!i||!n?cs:$(i.end,n.start)<0?ae(i.end,n.start):$(n.end,i.start)<0?ae(n.end,i.start):0}function Vt(t,{timeZone:e}){let r=new Set(t.order_numbers.map(Si).filter(Boolean)),i=Ri(t),n=o=>o.order_numbers.some(a=>r.has(Si(a)))?0:i&&Ri(o)===i?1:2;return(o,a)=>n(o)-n(a)||+!le(o)-+!le(a)||Ci(t,o,e)-Ci(t,a,e)||qt(o,a)}function ds(t,{today:e,timeZone:r}){if(t.archived||t.status==="cancelled")return!0;if(le(t))return!1;let i=M(t.delivered_at??t.status_time,r);return i!==null&&ae(i,e)>ls}function Ai(t,e,r){let i=[],n=[];for(let o of t)o.id===e.id||o.restricted||(ds(o,r)?n:i).push(o);return i.sort(Vt(e,r)),n.sort(qt),{likely:i,older:n}}function Pi(t,e){let r=e.toLowerCase().split(/\s+/).filter(Boolean);return r.length?t.filter(i=>{let n=[i.merchant,R(i),i.tracking_number,...i.order_numbers,...i.items].filter(Boolean).join(" ").toLowerCase();return r.every(o=>n.includes(o))}):[...t]}function Ii(t){let e=new Map;for(let r of t??[]){let i=e.get(r.parcel.id)??[];for(let n of r.candidates)i.some(o=>o.id===n.id)||i.push(n);e.set(r.parcel.id,i)}return e}function Li(t,e){let r=[],i=new Set,n=(o,a,c)=>{i.has(a.id)||(i.add(a.id),r.push({suggestionId:o,parcel:a,candidateId:c}))};for(let o of t??[])if(o.parcel.id===e)for(let a of o.candidates)n(o.id,a,a.id);else o.candidates.some(a=>a.id===e)&&n(o.id,o.parcel,e);return r}function Oi(t,e,r){return e?.kind==="delivered"||e?.kind==="returned"?null:Re(t.window_start,t.window_end,r)}function Ni(t){return!t.restricted&&R(t)===null}function Fi(t){return t!==void 0&&t>1?h(s.packages,{count:String(t)}):null}function ft(t){return t.restricted?s.privateParcel:gt(t.merchant)??s.unknownSeller}function Gt(t){if(t.restricted)return null;let e=gt(t.pickup_code);return e?h(s.pin,{code:e}):null}function Hi(t,e){let r=e.placement??null,i=[],n=R(t);if(n&&i.push(n),e.showStatus){let c=K(t.status);c&&i.push(c)}let o=Fi(e.count);o&&i.push(o),e.showRange&&r&&r.from!==r.to&&i.push(U(r.from,r.to,e.locale));let a=Oi(t,r,e.locale);return a&&i.push(a),Ni(t)&&i.push(s.carrierNotKnown),i.join(" \xB7 ")}var us=/^\d{1,3}\s*[x×]\s+/i,ps=/\s*(?:[,;(|[]|\s[-–—]\s)/,Mi=8;function gt(t){if(typeof t!="string")return null;let e=t.replace(/\s+/g," ").trim();return e||null}function Ui(t){let e=t.replace(us,""),r=e.search(ps);return(r>0?e.slice(0,r):e).trim()||t}function Bi(t){let e=Ui(t).split(" ").slice(0,3);for(;e.length>1&&e.join(" ").length>24;)e.pop();return e.join(" ")}function hs(t){let e=Ui(t).split(" "),r=e[0]??t;return r.length<4&&e.length>1?`${r} ${e[1]}`:r}function ce(t){if(t.restricted)return null;let e=(t.items??[]).map(gt).filter(n=>n!==null);if(e.length===0)return null;if(e.length===1)return e[0]??null;let r=e.map(e.length===2?Bi:hs),i=r.slice(0,Mi);return r.length>Mi&&i.push("\u2026"),`${h(s.itemsCount,{count:String(e.length)})} \xB7 ${i.join(", ")}`}function ms(t){let e=(t.items??[]).map(gt).filter(n=>n!==null),r=e[0];if(t.restricted||r===void 0)return null;let i=Bi(r);return e.length>1?h(s.itemsMore,{name:i,count:String(e.length-1)}):i}function zi(t){let e=t.length===1?t[0]:void 0;if(e!==void 0){let i=ce(e);return i?h(s.possibly,{items:i}):null}let r=[...new Set(t.map(ms).filter(i=>i!==null))];return r.length?h(s.possibly,{items:r.join(s.possiblyOr)}):null}function ji(t,e){let{locale:r}=e,i=e.placement??null,n=[ft(t)],o=Fi(e.count);o&&n.push(o);let a=R(t);a?n.push(h(s.carrierIs,{carrier:a})):Ni(t)&&n.push(s.carrierNotKnownLabel);let c=K(t.status),u=i?D(i.from,r):"";switch(i?.kind){case"delivered":n.push(h(s.deliveredOn,{date:u}));break;case"returned":n.push(h(s.returnedOn,{date:u}));break;case"pickup":n.push(h(s.readyForPickupSince,{date:u}));break;case"status":n.push(h(s.statusOn,{status:c,date:u}));break;case"eta":c&&n.push(c),n.push(h(s.expectedOn,{date:U(i.from,i.to,r)}));break;default:c&&n.push(c);break}let m=Oi(t,i,r);m&&n.push(m);let _=ce(t);if(_?n.push(_):e.possibly&&!t.restricted&&n.push(e.possibly),!t.restricted){t.ai?n.push(s.aiBadgeLabel):t.ai_filled&&n.push(s.aiFilledLabel),t.auto_merged&&n.push(s.autoMergedLabel),t.inferred&&n.push(s.inferredLabel);let p=Gt(t);p?n.push(p):t.has_code&&n.push(s.hasCode)}return(t.private||t.restricted)&&n.push(s.privateLabel),e.continuesBefore&&n.push(s.continuesBefore),e.continuesAfter&&n.push(s.continuesAfter),n.join(", ")}function Di(t){let e=t?.trim();return e?e.length<=6?e:`\u2026${e.replace(/[^0-9a-z]/gi,"").slice(-5)}`:null}function be(t,e){let r=null;if(le(t)){let a=C(t);r=a?U(a.start,a.end,e):null}else{let a=e.timeZone??Intl.DateTimeFormat().resolvedOptions().timeZone,c=t.delivered_at?t.delivered_undated:t.status_undated,u=M(t.delivered_at??t.status_time,a);r=c?s.dateNotKnownInline:u?U(u,u,e):null}let i=[R(t)??s.carrierNotKnown],n=Di(t.tracking_number);n&&i.push(h(s.numberTail,{tail:n}));let o=Di(t.order_numbers[0]);return o&&i.push(h(s.orderTail,{tail:o})),{title:ft(t),when:[K(t.status),r].filter(Boolean).join(" \xB7 "),carrier:i.join(" \xB7 "),items:ce(t)}}function je(t,e){let r=be(t,e);return[r.title,r.items,r.carrier,r.when].filter(Boolean).join(" \xB7 ")}function Yt(t,e){let r=[],i=new Map;for(let n of t){let o=e(n),a=o===null?void 0:i.get(o);if(a){a.push(n);continue}let c=[n];r.push(c),o!==null&&i.set(o,c)}return r}function Qt(t,...e){return t.restricted||t.shipment_group===null?null:JSON.stringify([t.shipment_group,t.status,...e])}function Ce(t,e){return t.id<e.id?-1:t.id>e.id?1:0}function Ki(t){return Yt(t,e=>Qt(e)).map(e=>{let r=[...e].sort(Ce);return{parcel:e.reduce((i,n)=>Ce(n,i)<0?n:i),members:r}})}function fs(t){return t.reduce((e,r)=>r!==null&&(e===null||r<e)?r:e,null)}function gs(t){return t.reduce((e,r)=>r!==null&&(e===null||r>e)?r:e,null)}function Wi(t,e){return e.length<2?t:{...t,window_start:fs(e.map(r=>r.window_start)),window_end:gs(e.map(r=>r.window_end)),ai:e.some(r=>r.ai),ai_filled:e.some(r=>r.ai_filled),private:e.some(r=>r.private),has_code:e.some(r=>r.has_code),pickup_code:_s(e),items:bs(t,e),auto_merged:e.find(r=>r.auto_merged)?.auto_merged??null,inferred:e.some(r=>r.inferred)}}function _s(t){let e=new Set;for(let r of t){let i=r.pickup_code?.trim();i&&e.add(i)}return e.size>0?[...e].join(", "):null}function bs(t,e){let r=[...t.items],i=new Set(r);for(let n of e)for(let o of n.items)i.has(o)||(i.add(o),r.push(o));return r}function qi(t,e){let r=e.shipment_group;if(r===null||e.restricted)return[];let i=t.filter(n=>n.shipment_group===r&&!n.restricted).sort((n,o)=>(n.tracking_number??"").localeCompare(o.tracking_number??"","en",{numeric:!0})||Ce(n,o));return i.length>1?i:[]}var Vi="var(--pink-color, #e91e63)",Ee="mdi:package-up",vs={email:s.pickupRuleEmail,next_working_day:s.pickupRuleNextWorkingDay,assumed:s.pickupRuleAssumed};function Gi(t){let e=t?.replace(/\s+/g," ").trim();return e||null}function ve(t,e){return t.received||$(t.day,e)<0}function ye(t){return t.restricted?s.privateReturn:Gi(t.merchant)??s.unknownSeller}function Zt(t){return t?vs[t]:null}function Yi(t){return t.restricted?null:R(t)}function Ke(t,e){return t.received?s.returnReceived:t.pickup===null?s.returnStarted:ve(t,e)?s.returnPickedUp:s.returnPickup}function Qi(t,e){let r=Ke(t,e),i=Yi(t);return i?`${r} \xB7 ${i}`:r}function Zi(t,e,r){let i=t.restricted?null:Gi(t.merchant),n=[t.restricted?s.privateReturn:i?h(s.returnTo,{merchant:i}):s.returnPlain],o=D(t.day,e);if(t.pickup===null)n.push(h(s.returnStartedOn,{date:o}));else if(ve(t,r))$(t.day,r)<=0&&n.push(h(s.pickedUpOn,{date:o}));else{n.push(h(s.pickupOn,{date:o}));let u=Zt(t.pickup_rule);u&&n.push(u)}t.received&&n.push(s.receivedByShopLabel);let a=Yi(t);a&&n.push(h(s.carrierIs,{carrier:a}));let c=ce(t);return c&&n.push(c),(t.private||t.restricted)&&n.push(s.privateLabel),n.join(", ")}function Ji(t,e){return t.filter(r=>r.parcel_ids.includes(e))}function Xt(t){return`.chip[data-parcels~="${CSS.escape(t)}"] button.chip-main`}function Xi(t,e,r,i){let n=e?"true":"false";return l`<div class="merge-note">
    <ha-icon icon=${t.icon} aria-hidden="true"></ha-icon>
    <span class="merge-label"
      >${t.label}${t.detail?l` <span class="merge-detail">${t.detail}</span>`:d}</span
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
  </div>`}function ys(t,e,r){let i=r&&(t.tracking_number?.trim()??null)||null;return{title:i?`${e} ${i}`:e,detail:i}}function $s(t,e,r){let{title:i,detail:n}=e;return Xi({icon:"mdi:call-merge",label:s.autoMerged,detail:n,undoLabel:h(s.undoMergeLabel,{title:i}),keepLabel:h(s.keepMergeLabel,{title:i})},r.busy,()=>r.onUndoMerge(t),()=>r.onKeepMerge(t))}function ks(t,e,r){let{title:i,detail:n}=e;return Xi({icon:"mdi:package-variant-closed-check",label:s.inferred,detail:n,undoLabel:h(s.undoInferredLabel,{title:i}),keepLabel:h(s.keepInferredLabel,{title:i})},r.busy,()=>r.onUndoInferred(t),()=>r.onKeepInferred(t))}var Jt="\xA0";function _t(t,e){let{locale:r}=e,i=e.placement??null,n=e.members&&e.members.length>1?e.members:[t],o=n.length>1,a=Wi(t,n),c=P(a),u=Gt(a),m=ce(a),_=m===null&&!a.restricted?e.possibly??null:null,p=ji(a,{locale:r,placement:i,count:n.length,continuesBefore:e.continuesBefore,continuesAfter:e.continuesAfter,possibly:_}),g=Hi(a,{locale:r,placement:i,count:n.length,showStatus:e.showStatus,showRange:e.showRange}),f={chip:!0,"cont-before":e.continuesBefore===!0,"cont-after":e.continuesAfter===!0,returned:a.status==="returned"},v={...e.position,"--chip-color":ze(a.status)},T=l`<span class="chip-row" aria-hidden=${a.restricted?"true":d}>
    ${e.continuesBefore?l`<span class="cont">‹</span>`:d}
    ${a.status==="delivered"?l`<span class="check">✓</span>`:d}
    <span class="chip-text">
      <span class=${fe({"chip-title":!0,unknown:!a.restricted&&!a.merchant?.trim()})}
        >${ft(a)}</span
      >
      <span class="chip-line">
        <span class="chip-meta">${g||Jt}</span>
        ${u?l`<span class="chip-pin">${u}</span>`:d}
      </span>
      <span
        class=${fe({"chip-items":!0,unknown:m===null&&_===null&&!a.restricted,possibly:_!==null})}
        >${m??_??(a.restricted?Jt:s.itemsNotKnown)}</span
      >
    </span>
    ${(a.ai||a.ai_filled)&&!a.restricted?l`<span class="badge ai">${s.aiBadge}</span>`:d}
    ${a.has_code&&!u&&!a.restricted?l`<ha-icon class="lock" icon="mdi:dialpad" title=${s.hasCode}></ha-icon>`:d}
    ${a.private||a.restricted?l`<ha-icon class="lock" icon="mdi:lock"></ha-icon>`:d}
    ${e.continuesAfter?l`<span class="cont">›</span>`:d}
  </span>`;return a.restricted?l`<div class=${fe(f)} style=${N(v)}>
      <div class="chip-main" title=${p}>
        <span class="sr-only">${p}</span>
        ${T}
      </div>
    </div>`:l`<div
    class=${fe(f)}
    style=${N(v)}
    data-parcel-id=${a.id}
    data-parcels=${n.map(S=>S.id).join(" ")}
  >
    <button
      type="button"
      class="chip-main"
      aria-haspopup="dialog"
      aria-label=${p}
      title=${p}
      @click=${S=>e.onOpen(t,S.currentTarget)}
    >
      ${T}
    </button>
    ${n.map(S=>{let w=ys(S,c,o);return l`${S.auto_merged?$s(S,w,e):d}${S.inferred?ks(S,w,e):d}`})}
  </div>`}function er(t){return`.chip[data-return-id="${CSS.escape(t)}"] button.chip-main`}function en(t,e){let r=Zi(t,e.locale,e.today),i=ce(t),n={chip:!0,return:!0,done:ve(t,e.today)},o={...e.position,"--chip-color":Vi},a=l`<span class="chip-row" aria-hidden=${t.restricted?"true":d}>
    <ha-icon class="ret-icon" icon=${Ee}></ha-icon>
    <span class="chip-text">
      <span class="chip-title">${ye(t)}</span>
      <span class="chip-line">
        <span class="chip-meta">${Qi(t,e.today)}</span>
      </span>
      <span class="chip-items">${i??Jt}</span>
    </span>
    ${t.private||t.restricted?l`<ha-icon class="lock" icon="mdi:lock"></ha-icon>`:d}
  </span>`;return t.restricted?l`<div class=${fe(n)} style=${N(o)}>
      <div class="chip-main" title=${r}>
        <span class="sr-only">${r}</span>
        ${a}
      </div>
    </div>`:l`<div class=${fe(n)} style=${N(o)} data-return-id=${t.id}>
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
  </div>`}function tn(t,e){return e&&!t.restricted&&!t.archived&&le(t)&&C(t)===null}function bt(t){return typeof t=="number"&&Number.isInteger(t)&&t>0?t:0}function tr(t){let e=t!==null&&typeof t=="object"?t:{};return{read:bt(e.read),queued:bt(e.queued),gone:bt(e.gone),failed:bt(e.failed)}}function vt(t,e,r){return t<=0?null:t===1?e:h(r,{count:t})}function rn(t,e){if(t.read+t.gone+t.failed===0)return s.checkAgainNoEmails;let r=[vt(t.read,s.checkAgainReadOne,s.checkAgainReadMany),vt(t.gone,s.checkAgainGoneOne,s.checkAgainGoneMany),vt(t.failed,s.checkAgainFailedOne,s.checkAgainFailedMany)];return t.queued>0?r.push(vt(t.queued,s.checkAgainQueuedOne,s.checkAgainQueuedMany),e.mode==="suggest"?s.checkAgainSuggest:s.checkAgainAuto):t.read>0&&r.push(e.enabled?s.checkAgainNothingForAi:s.checkAgainAiOff),r.filter(i=>i!==null).join(" ")}function E(t){return typeof t=="object"&&t!==null&&!Array.isArray(t)}function b(t){return typeof t=="string"?t:null}function y(t){return typeof t=="string"?t:""}function O(t){return Array.isArray(t)?t.filter(e=>typeof e=="string"):[]}function te(t){return typeof t=="string"&&t!==""?t:null}function rr(t){return Number.isSafeInteger(t)&&t>0?t:0}function ws(t){return typeof t=="number"&&Number.isFinite(t)&&t>=0?t:null}function Q(t,e){if(!Array.isArray(t))return[];let r=[];for(let i of t){let n=e(i);n!==null&&r.push(n)}return r}function xs(t){return t==="shop"||t==="return"||t==="quiet"?t:null}function We(t){return t==="ai"||t==="manual"||t==="seventeentrack"||t==="parcelapp"?t:"parser"}function Ss(t){return typeof t=="string"&&t?We(t):null}function Rs(t){return!E(t)||!te(t.origin)?null:{origin:y(t.origin),at:y(t.at),reason:y(t.reason)}}function yt(t){if(!E(t))return null;let e=te(t.id);return e?{id:e,merchant:b(t.merchant),seller:b(t.seller),name:b(t.name),carrier:b(t.carrier),carrier_name:b(t.carrier_name),tracking_number:b(t.tracking_number),tracking_url:b(t.tracking_url),status:y(t.status),status_time:b(t.status_time),status_undated:t.status_undated===!0,eta_start:b(t.eta_start),eta_end:b(t.eta_end),window_start:b(t.window_start),window_end:b(t.window_end),eta_source:Ss(t.eta_source),delivered_at:b(t.delivered_at),delivered_undated:t.delivered_undated===!0,inferred:t.inferred===!0,inferred_reason:xs(t.inferred_reason),pickup_point:b(t.pickup_point),pickup_code:b(t.pickup_code),has_code:t.has_code===!0,order_numbers:O(t.order_numbers),references:O(t.references),items:O(t.items),private:t.private===!0,owners:O(t.owners),source:We(t.source),ai:t.ai===!0,ai_filled:t.ai_filled===!0,auto_merged:Rs(t.auto_merged),provisional:t.provisional===!0,archived:t.archived===!0,origins:O(t.origins),shipment_group:te(t.shipment_group),restricted:t.restricted===!0}:null}function Ts(t){return E(t)?{kind:y(t.kind),merchant:b(t.merchant),carrier:b(t.carrier),tracking_numbers:O(t.tracking_numbers),order_numbers:O(t.order_numbers),eta_start:b(t.eta_start),eta_end:b(t.eta_end),window_start:b(t.window_start),window_end:b(t.window_end),pickup_point:b(t.pickup_point),pickup_code:b(t.pickup_code),items:O(t.items),reference:b(t.reference)}:null}function Cs(t){if(!E(t))return null;let e=te(t.id);return e?{id:e,created:y(t.created),received:b(t.received),sender:y(t.sender),sender_domain:y(t.sender_domain),subject:y(t.subject),mailbox_owner:b(t.mailbox_owner),reason:y(t.reason),authenticated:t.authenticated===!0,trusted_sender:t.trusted_sender===!0,checks:Ps(t.checks),fill:t.fill===!0,errors:As(t.errors),source:t.source==="ai"?"ai":"parser",suggestion:Ts(t.suggestion)}:null}var Es=/^[a-z0-9_]{1,40}$/;function As(t){if(!Array.isArray(t))return[];let e=t.filter(r=>typeof r=="string"&&Es.test(r));return[...new Set(e)]}function Ps(t){if(!E(t))return null;let e=rr(t.headers),r=t.used;return{headers:e,servers:Array.isArray(t.servers)?t.servers.map(i=>typeof i=="string"?i:""):[],used:Number.isSafeInteger(r)&&r>=0&&r<e?r:null,dkim:y(t.dkim),dmarc:y(t.dmarc),spf:y(t.spf),originals:rr(t.originals)}}function Is(t){if(!E(t))return null;let e=te(t.id);return e?{id:e,created:y(t.created),received:b(t.received),sender:y(t.sender),sender_domain:y(t.sender_domain),subject:y(t.subject)}:null}function Ls(t){if(!E(t))return null;let e=te(t.id),r=yt(t.parcel),i=Q(t.candidates,yt);return!e||!r||!i.length?null:{id:e,reason:y(t.reason),merchant:b(t.merchant),day:z(t.day)?t.day:null,parcel:r,candidates:i}}function Ms(t){return t==="suggest"||t==="auto"?t:"off"}function Ds(t,e=Date.now()){let r=E(t)?t:{},i=te(r.time_zone)??"UTC",n=z(r.today)?r.today:M(new Date(e).toISOString(),i)??"1970-01-01";return{user_is_admin:r.user_is_admin===!0,ai_enabled:r.ai_enabled===!0,ai_mode:Ms(r.ai_mode),ai_queue:rr(r.ai_queue),ai_queue_seconds:ws(r.ai_queue_seconds),dashboard_url:y(r.dashboard_url),seventeentrack:r.seventeentrack===!0,time_zone:i,today:n}}function nn(t,e=Date.now()){let r=E(t)?t:{};return{parcels:Q(r.parcels,yt),returns:Q(r.returns,Fs),review:Q(r.review,Cs),merge_suggestions:Q(r.merge_suggestions,Ls),filtered:Q(r.filtered,Is),settings:Ds(r.settings,e)}}function Os(t){return t==="email"||t==="next_working_day"||t==="assumed"?t:null}function Ns(t){return E(t)?{time:b(t.time),label:y(t.label),source:We(t.source)}:null}function Fs(t){if(!E(t))return null;let e=te(t.id);return!e||!z(t.day)?null:{id:e,merchant:b(t.merchant),carrier:b(t.carrier),carrier_name:b(t.carrier_name),tracking_number:b(t.tracking_number),tracking_url:b(t.tracking_url),day:t.day,pickup:z(t.pickup)?t.pickup:null,pickup_rule:Os(t.pickup_rule),started:b(t.started),received:t.received===!0,order_numbers:O(t.order_numbers),items:O(t.items),parcel_ids:O(t.parcel_ids),emails:Q(t.emails,Ns),private:t.private===!0,owners:O(t.owners),archived:t.archived===!0,restricted:t.restricted===!0}}function Hs(t){return t==="inferred"||t==="inferred_return"||t==="quiet"?t:We(t)}function Us(t){return E(t)?{time:y(t.time),status:y(t.status),source:Hs(t.source),label:y(t.label),undated:t.undated===!0}:null}function Bs(t){return E(t)?{id:y(t.id),merchant:b(t.merchant),number:y(t.number),placed_at:b(t.placed_at),parcel_ids:O(t.parcel_ids)}:null}function zs(t){if(!E(t))return null;let e=te(t.id);return e?{id:e,label:y(t.label),source:We(t.source),time:b(t.time)}:null}function sn(t){if(!E(t))return null;let e=yt(t.parcel);return e?{parcel:e,timeline:Q(t.timeline,Us),orders:Q(t.orders,Bs),origins:Q(t.origins,zs)}:null}function $t(t){if(typeof t!="string")return null;let e=t.trim();if(!e)return null;let r;try{r=new URL(e)}catch{return null}return r.protocol!=="https:"||!r.hostname||r.username||r.password?null:r.href}var js={weekday:"short",day:"numeric",month:"short",year:"numeric"},on={eta_start:"",eta_end:"",window_start:"",window_end:""},Ks=6;function Ws(t){return t.map((e,r)=>({entry:e,index:r,time:G(e.time)??-1/0})).sort((e,r)=>r.time-e.time||r.index-e.index).map(({entry:e})=>e)}var ir=class extends oe{static properties={snapshot:{attribute:!1},locale:{attribute:!1},_parcelId:{state:!0},_details:{state:!0},_loading:{state:!0},_loadError:{state:!0},_mode:{state:!0},_copyState:{state:!0},_dateForm:{state:!0},_formError:{state:!0},_mergeTarget:{state:!0},_mergeQuery:{state:!0},_mergeOlder:{state:!0},_mergeHint:{state:!0},_splitSelection:{state:!0},_pendingPrivate:{state:!0},_checking:{state:!0},_checkStatus:{state:!0}};static styles=[H,xe,x`
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
    `];_request=0;_checkRun=0;_loadedKey="";constructor(){super(),this.snapshot=null,this.locale=Se(void 0),this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._copyState="idle",this._dateForm=on,this._formError=null,this._mergeTarget="",this._mergeQuery="",this._mergeOlder=!1,this._mergeHint=!1,this._splitSelection=[],this._pendingPrivate=null,this._checking=!1,this._checkStatus=null}async open(e,r=null){this._parcelId=e,this._details=null,this._loadError=null,this._mode="view",this._copyState="idle",this._formError=null,this._pendingPrivate=null,this._checkRun+=1,this._checking=!1,this._checkStatus=null,this._load(),await this.showDialog(r)}_switchTo(e){this._busy||e===this._parcelId||(this._parcelId=e,this._details=null,this._loadError=null,this._error=null,this._mode="view",this._copyState="idle",this._formError=null,this._pendingPrivate=null,this._checkStatus=null,this._load(),this.focusAfterRender("[data-current-package]"))}dialogClosed(){this._request+=1,this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._pendingPrivate=null,this._checkRun+=1,this._checking=!1,this._checkStatus=null}canLightDismiss(){return this._mode==="view"&&!this._busy}willUpdate(e){if(super.willUpdate(e),!e.has("snapshot")||!this.isOpen||!this.snapshot)return;this._pendingPrivate=null;let r=this.snapshot.parcels.find(i=>i.id===this._parcelId);r&&JSON.stringify(r)!==this._loadedKey&&this._load()}get _parcel(){let e=this._parcelId;return e===null?null:this.snapshot?this.snapshot.parcels.find(r=>r.id===e)??null:this._details?.parcel??null}async _load(){let e=this.hass,r=this._parcelId;if(!e||r===null)return;let i=++this._request,n=this.snapshot?.parcels.find(o=>o.id===r);this._loadedKey=n?JSON.stringify(n):"",this._loading=!0,this._loadError=null;try{let o=await V(e,"get",{parcel_id:r});if(i!==this._request)return;let a=sn(o);if(!a)throw new Error(s.unknownError);this._details=a}catch(o){i===this._request&&(this._loadError=B(o))}finally{i===this._request&&(this._loading=!1)}}renderContent(){let e=this._parcel;return l`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">
            ${e?P(e):s.details}
          </h2>
          ${e?this._renderBadges(e):d}
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
          </div>`:d}
      ${e&&this._mode==="view"?this._renderCheckStatus():d}
      ${e&&!e.restricted?this._renderActions(e):d}
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
          </div>`:d}
    </div>`}_renderBadges(e){let r=e.ai?s.aiBadgeLabel:s.aiFilledLabel;return l`<div class="dialog-badges">
      <span class="badge" style=${N({"--badge-color":ze(e.status)})}>
        ${K(e.status)}
      </span>
      ${(e.ai||e.ai_filled)&&!e.restricted?l`<span class="badge ai" title=${r}>
            ${s.aiBadge}<span class="sr-only">, ${r}</span>
          </span>`:d}
      ${e.private||e.restricted?l`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${s.private}
          </span>`:d}
      ${e.provisional?l`<span class="badge info">${s.provisional}</span>`:d}
      ${this._returnsOf(e).length?l`<span class="badge return">
            <ha-icon icon=${Ee} aria-hidden="true"></ha-icon>${s.returnBadge}
          </span>`:d}
      ${e.archived?l`<span class="badge">${s.archived}</span>`:d}
    </div>`}_returnsOf(e){return e.restricted?[]:Ji(this.snapshot?.returns??[],e.id)}_renderBody(e){if(!e)return this.snapshot||!this._loading&&!this._loadError?l`<p class="empty">${s.notFound}</p>`:this._renderLoadState();switch(this._mode){case"date":return this._renderDateForm();case"merge":return this._renderMerge(e);case"split":return this._renderSplit();case"archive":return l`<p>${s.archiveQuestion}</p>`;default:return this._renderView(e)}}_renderLoadState(){return this._loadError?l`<div class="alert error" role="alert">
        <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
        <span class="grow">${h(s.detailsError,{message:this._loadError})}</span>
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
          </div>`:d}
      ${!r&&e.auto_merged?this._renderMergeNotice(e):d}
      ${!r&&e.inferred?this._renderInferredNotice(e):d}
      ${!r&&e.provisional?l`<p class="hint">${s.provisionalHint}</p>`:d}
      ${r?d:this._renderPossible(e)}
      ${this._renderFacts(e)}
      ${r?d:l`<label class="check-row switch-row">
            <input
              type="checkbox"
              role="switch"
              .checked=${L(this._pendingPrivate??e.private)}
              aria-disabled=${this._busy?"true":"false"}
              @click=${this._onPrivateClick}
              @change=${this._togglePrivate}
            />
            <span>${s.fieldPrivate}</span>
          </label>`}
      <h3 class="section-title">${s.timeline}</h3>
      ${this._details?this._renderTimeline(this._details.timeline):this._renderLoadState()}
    `}_renderPossible(e){let r=Li(this.snapshot?.merge_suggestions,e.id);if(!r.length)return d;let i=this.locale,n=this._busy?"true":"false",o=P(e);return l`<section class="possible" aria-labelledby="possible-title">
      <h3 class="section-title" id="possible-title">${s.possibleMatches}</h3>
      <p class="hint">${s.possibleMatchesHint}</p>
      <ul class="possible-list">
        ${r.map(a=>{let c=be(a.parcel,i),u=je(a.parcel,i);return l`<li class="possible-item" data-possible=${a.parcel.id}>
            <span class="merge-lines">
              <span class="merge-line"><strong>${c.title}</strong> · ${c.when}</span>
              <span class="merge-line muted">${c.carrier}</span>
              <span class="merge-line items ${c.items?"":"muted"}">
                ${c.items??s.itemsNotKnown}
              </span>
            </span>
            <span class="possible-actions">
              <button
                type="button"
                class="btn"
                data-accept
                aria-label=${h(s.mergeSuggestedLabel,{candidate:u,title:o})}
                aria-disabled=${n}
                @click=${()=>this._acceptPossible(a)}
              >
                ${s.mergeSuggested}
              </button>
              <button
                type="button"
                class="btn"
                data-dismiss
                aria-label=${h(s.notThisOneLabel,{candidate:u,title:o})}
                aria-disabled=${n}
                @click=${()=>this._dismissPossible(a)}
              >
                ${s.notThisOne}
              </button>
            </span>
          </li>`})}
      </ul>
    </section>`}_renderMergeNotice(e){let r=ht(e.auto_merged?.reason),i=this._busy?"true":"false",n=P(e);return l`<div class="alert warning">
      <ha-icon icon="mdi:call-merge" aria-hidden="true"></ha-icon>
      <span class="grow">
        ${r?h(s.mergedNotice,{reason:r}):s.mergedNoticeNoReason}
      </span>
      <button
        type="button"
        class="btn"
        aria-label=${h(s.undoMergeLabel,{title:n})}
        aria-disabled=${i}
        @click=${this._undoMerge}
      >
        ${s.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${h(s.keepMergeLabel,{title:n})}
        aria-disabled=${i}
        @click=${this._keepMerge}
      >
        ${s.keep}
      </button>
    </div>`}_renderInferredNotice(e){let r=this._busy?"true":"false",i=P(e);return l`<div class="alert warning">
      <ha-icon icon="mdi:package-variant-closed-check" aria-hidden="true"></ha-icon>
      <span class="grow">${yi(e)}</span>
      <button
        type="button"
        class="btn"
        aria-label=${h(s.undoInferredLabel,{title:i})}
        aria-disabled=${r}
        @click=${this._undoInferred}
      >
        ${s.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${h(s.keepInferredLabel,{title:i})}
        aria-disabled=${r}
        @click=${this._keepInferred}
      >
        ${s.keep}
      </button>
    </div>`}_renderFacts(e){let r=this.locale,i=C(e),n=Re(e.window_start,e.window_end,r),o=R(e),a=e.restricted?null:$t(e.tracking_url),c=e.tracking_number?.trim()??"",u=this._details?.orders??[],m=qi(this.snapshot?.parcels??[],e),_=this._details?.parcel.id===e.id?this._details.parcel:null,p=e.has_code?_?.pickup_code??null:null,g=this._returnsOf(e),f=(w,xn)=>l`<div><dt>${w}</dt><dd>${xn}</dd></div>`,v=e.status_undated?` \xB7 ${s.dateNotKnownInline}`:e.status_time?` \xB7 ${h(s.sinceDate,{date:A(e.status_time,r)})}`:"",T=vi(e),S=bi(e);return l`<dl class="facts">
      ${f(s.status,`${K(e.status)}${v}`)}
      ${e.delivered_undated?f(s.delivered,s.dateNotKnown):e.delivered_at?f(s.delivered,A(e.delivered_at,r)):d}
      ${i?f(s.expected,`${U(i.start,i.end,r,js)}${T?` \xB7 ${T}`:""}`):d}
      ${n?f(s.timeWindow,n):d}
      ${g.length?f(s.returnBadge,l`<ul>
              ${g.map(w=>this._renderReturnLink(w))}
            </ul>`):d}
      ${o||a||!e.restricted?f(s.carrier,l`${o??(e.restricted?"":s.notKnownYet)}${a?l`<a class="link" href=${a} target="_blank" rel="noopener noreferrer">
                  ${s.trackOnline}<span class="sr-only"> ${s.opensInNewTab}</span>
                  <ha-icon icon="mdi:open-in-new" aria-hidden="true"></ha-icon>
                </a>`:d}`):d}
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
          </div>`:d}
      ${m.length?f(s.packagesInShipment,l`<ul class="packages">
              ${m.map(w=>this._renderPackage(w,e.id))}
            </ul>`):d}
      ${e.merchant?f(s.merchant,e.merchant):d}
      ${e.seller?f(s.seller,e.seller):d}
      ${S?f(s.parcelAppName,S):d}
      ${u.length?f(s.orders,l`<ul>
              ${u.map(w=>l`<li>
                    ${w.number}${w.placed_at?` \xB7 ${A(w.placed_at,r)}`:""}
                  </li>`)}
            </ul>`):e.order_numbers.length?f(s.orders,e.order_numbers.join(", ")):d}
      ${e.references.length?f(s.references,e.references.join(", ")):d}
      ${e.items.length?f(s.items,l`<ul>
              ${e.items.map(w=>l`<li>${w}</li>`)}
            </ul>`):d}
      ${e.pickup_point?f(s.pickupPoint,e.pickup_point):d}
      ${p?f(s.pickupCode,p):d}
      ${e.restricted?d:f(s.parcelId,e.id)}
    </dl>`}_renderReturnLink(e){let r=this.snapshot?.settings.today??"",i=`${Ke(e,r)} \xB7 ${D(e.day,this.locale)}`;return e.restricted?l`<li>${i}</li>`:l`<li>
      <button
        type="button"
        class="link-btn"
        aria-haspopup="dialog"
        aria-disabled=${this._busy?"true":"false"}
        @click=${()=>this._openReturn(e.id)}
      >
        ${i}
      </button>
    </li>`}_openReturn(e){this._busy||(this.closeDialog(),this.dispatchEvent(new CustomEvent(ii,{detail:e})))}_renderPackage(e,r){let i=this.locale,n=e.tracking_number?.trim()||P(e),o=C(e),a=e.delivered_undated?s.dateNotKnownInline:e.delivered_at?A(e.delivered_at,i):o?U(o.start,o.end,i):"",c=[K(e.status),a].filter(Boolean).join(" \xB7 ");return e.id===r?l`<li aria-current="true" tabindex="-1" data-current-package>
        <strong>${n}</strong>${c?` \xB7 ${c}`:""}
      </li>`:l`<li>
      <button
        type="button"
        class="link-btn"
        aria-label=${h(s.showPackage,{name:n})}
        aria-disabled=${this._busy?"true":"false"}
        @click=${()=>this._switchTo(e.id)}
      >
        ${n}</button
      >${c?` \xB7 ${c}`:""}
    </li>`}_renderTimeline(e){if(!e.length)return l`<p class="muted">${s.noTimeline}</p>`;let r=this.locale;return l`<ol class="timeline">
      ${Ws(e).map(i=>{let n=K(i.status),o=i.label.trim(),c=[i.undated?s.dateNotKnown:A(i.time,r),Te(i.source)].filter(Boolean).join(" \xB7 ");return l`<li style=${N({"--dot-color":ze(i.status)})}>
          <span class="dot" aria-hidden="true"></span>
          <div class="entry-title">${n}</div>
          ${o&&o!==n?l`<div>${o}</div>`:d}
          ${c?l`<div class="entry-meta">${c}</div>`:d}
        </li>`})}
    </ol>`}_renderDateForm(){let e=this._dateForm,r=this._formError,i=(n,o,a,c=!1)=>{let u=r?.field===n;return l`<label class="field">
        <span class="field-label">${o}</span>
        <input
          type=${a}
          name=${n}
          .value=${L(e[n])}
          ?data-first=${c}
          aria-invalid=${u?"true":"false"}
          aria-describedby=${u?"date-error":d}
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
          </div>`:d}
    </form>`}_renderMerge(e){let{pool:r,shown:i,target:n}=this._mergeChoice(e),o=r.likely.length+r.older.length;if(!o)return l`<p class="empty">${s.noMergeCandidates}</p>`;let a=this._mergeQuery.trim()!=="",c=o>Ks,u=this._mergeOlder&&!a?r.likely.length:-1,m=!a&&!this._mergeOlder&&r.older.length>0;return l`<p id="merge-intro">${s.mergeIntro}</p>
      ${c?l`<label class="field">
            <span class="field-label">${s.mergeSearch}</span>
            <input
              type="search"
              data-first
              autocomplete="off"
              placeholder=${s.mergeSearchPlaceholder}
              .value=${L(this._mergeQuery)}
              @input=${this._onMergeQuery}
            />
          </label>`:d}
      <fieldset class="merge-list" aria-describedby="merge-intro">
        <legend class="sr-only">${s.mergeChoose}</legend>
        ${i.map((_,p)=>this._renderCandidate(_,{checked:_.id===n,first:!c&&p===0,olderFirst:p===u}))}
        ${a&&!i.length?l`<p class="empty">${s.mergeNoMatch}</p>`:d}
      </fieldset>
      ${m?l`<button
            type="button"
            class="link-btn"
            ?data-first=${!c&&!i.length}
            @click=${this._showOlderMerge}
          >
            ${h(s.mergeShowOlder,{count:String(r.older.length)})}
          </button>`:d}
      ${this._mergeHint&&!n?l`<p class="hint merge-hint" role="alert">${s.mergeChooseFirst}</p>`:d}`}_renderCandidate(e,r){let i=be(e,this.locale);return l`<label class="merge-option">
      <input
        type="radio"
        name="merge-target"
        value=${e.id}
        .checked=${L(r.checked)}
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
        ${e.map((i,n)=>{let o=i.time?A(i.time,r):"";return l`<label class="check-row">
            <input
              type="checkbox"
              .value=${i.id}
              .checked=${L(this._splitSelection.includes(i.id))}
              ?data-first=${n===0}
              @change=${this._onSplitChange}
            />
            <span>
              ${i.label.trim()||Te(i.source)}${o?l`<span class="muted"> · ${o}</span>`:d}
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
              </button>`:d}
        </div>`}case"split":{let n=zt(this._splitSelection,this._details?.origins.length??0);return l`<div class="dialog-actions">
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
          ${tn(e,this.snapshot?.settings.user_is_admin===!0)?l`<button
                type="button"
                class="btn"
                data-check-again
                title=${s.checkAgainHint}
                aria-disabled=${r}
                @click=${this._checkAgain}
              >
                ${this._checking?s.checkingAgain:s.checkAgain}
              </button>`:d}
          <button type="button" class="btn" data-mode="merge" @click=${this._startMerge}>
            ${s.mergeWith}
          </button>
          ${n?l`<button type="button" class="btn" data-mode="split" @click=${this._startSplit}>
                ${s.split}
              </button>`:d}
          ${e.archived?d:l`<button
                type="button"
                class="btn danger"
                data-mode="archive"
                @click=${this._startArchive}
              >
                ${s.archive}
              </button>`}
          ${_e(e.status)?l`<span class="spacer"></span>
                <button
                  type="button"
                  class="btn primary"
                  aria-disabled=${r}
                  @click=${this._markDelivered}
                >
                  <ha-icon icon="mdi:check" aria-hidden="true"></ha-icon>${s.markDelivered}
                </button>`:d}
        </div>`}}}_setMode(e){this._mode=e,this._error=null,this._formError=null,this.focusAfterRender(e==="archive"?"[data-cancel]":"[data-first], [data-cancel]")}_backToView(){let e=this._mode;this._mode="view",this._error=null,this._formError=null,this.focusAfterRender(`[data-mode="${e}"]`)}_editDate(){let e=this._parcel;this._dateForm=e?li(e):on,this._setMode("date")}_startMerge(){this._mergeTarget="",this._mergeQuery="",this._mergeOlder=!1,this._mergeHint=!1,this._setMode("merge")}_startSplit(){this._splitSelection=[],this._setMode("split")}_startArchive(){this._setMode("archive")}_parcelService(e,r,i){let n=this.hass,o=this._parcel;!n||!o||this.runAction(()=>ne(n,e,{parcel_id:o.id,...r}),i)}_confirm(){this._parcelService("update",{confirm:!0})}_undoMerge(){this._parcelService("undo_merge",{})}_keepMerge(){this._parcelService("update",{confirm_merge:!0})}_undoInferred(){this._parcelService("undo_delivery",{})}_keepInferred(){this._parcelService("update",{confirm_delivery:!0})}_markDelivered(){this._parcelService("mark_delivered",{})}async _checkAgain(){let e=this.hass,r=this._parcel;if(!e||!r||this._busy)return;let i=++this._checkRun,n=tr(null);this._checkStatus=null,this._checking=!0,await this.runAction(async()=>{let o=await V(e,"parcel/check_again",{parcel_id:r.id});n=tr(o)},()=>{let o=this.snapshot?.settings;this._checkStatus=rn(n,{enabled:o?.ai_enabled===!0,mode:o?.ai_mode??"off"})}),i===this._checkRun&&(this._checking=!1)}_dismissCheckStatus(){this._checkStatus=null}_archive(){this._parcelService("archive",{},()=>this.closeDialog())}_onPrivateClick(e){this._busy&&e.preventDefault()}_togglePrivate(e){let r=e.currentTarget.checked,i=this.hass,n=this._parcel;!i||!n||this._busy||(this._pendingPrivate=r,this.runAction(async()=>{try{await ne(i,"update",{parcel_id:n.id,private:r})}catch(o){throw this._pendingPrivate=null,o}}))}_onDateInput(e){let r=e.currentTarget,i=r.name;this._dateForm={...this._dateForm,[i]:r.value},this._formError=null}_saveDate(e){e.preventDefault();let r=this._parcel;if(!r||this._busy)return;let i=this._dateForm,n=dt(i);if(n){this._formError=n,this.focusAfterRender(`[name="${n.field}"]`);return}let o=ci(r.id,i);this._parcelService("update",o,()=>this._backToView())}_mergePool(e){let r=this.snapshot;return r?Ai(r.parcels,e,{today:r.settings.today,timeZone:r.settings.time_zone}):{likely:[],older:[]}}_mergeChoice(e){let r=this._mergePool(e),i=this._mergeQuery.trim(),n=r.likely;i?n=Pi([...r.likely,...r.older],i):this._mergeOlder&&(n=[...r.likely,...r.older]);let o=n.some(a=>a.id===this._mergeTarget)?this._mergeTarget:"";return{pool:r,shown:n,target:o}}_onMergeTarget(e){this._mergeTarget=e.currentTarget.value,this._mergeHint=!1}_onMergeQuery(e){this._mergeQuery=e.currentTarget.value}_showOlderMerge(){this._mergeOlder=!0,this.focusAfterRender("[data-older-first]")}_acceptPossible(e){let r=this.hass;if(!r)return;let i=null;this.runAction(async()=>{let n=await V(r,"suggestion/accept",{suggestion_id:e.suggestionId,parcel_id:e.candidateId});i=typeof n?.parcel_id=="string"?n.parcel_id:null},()=>{i!==null&&i!==this._parcelId&&(this._parcelId=i,this._details=null,this._loadError=null,this._load()),this.focusAfterRender("[data-autofocus]")})}_dismissPossible(e){let r=this.hass;r&&this.runAction(()=>V(r,"suggestion/dismiss",{suggestion_id:e.suggestionId,parcel_id:e.candidateId}),()=>{this.focusAfterRender("[data-autofocus]")})}_merge(){let e=this.hass,r=this._parcel;if(!e||!r)return;let{target:i}=this._mergeChoice(r);if(!i){this._mergeHint=!0,this.focusAfterRender('input[name="merge-target"]');return}this.runAction(()=>ne(e,"merge",{parcel_ids:[r.id,i]}),()=>this._backToView())}_onSplitChange(e){let r=e.currentTarget,i=this._splitSelection.filter(n=>n!==r.value);this._splitSelection=r.checked?[...i,r.value]:i}_split(){let e=this._details?.origins.length??0;zt(this._splitSelection,e)&&this._parcelService("split",{origins:[...this._splitSelection]},()=>this._backToView())}async _copy(e){let r=e.currentTarget,i=this._parcel?.tracking_number?.trim();if(!i)return;this._copyState="idle";try{if(!navigator.clipboard?.writeText)throw new Error("Clipboard API unavailable");await navigator.clipboard.writeText(i),this._copyState="copied";return}catch{}let n=this.renderRoot.querySelector("#tracking-number");n?.focus(),n?.select();let o=!1;try{o=document.execCommand("copy")}catch{o=!1}this._copyState=o?"copied":"failed",o&&r.focus()}};F("parcels-details-dialog",ir);var nr=["all","active","recent","completed"],kt={all:s.filterAll,active:s.filterActive,recent:s.filterRecent,completed:s.filterCompleted},wt="parcels-filter",xt="parcels-filter-changed";function sr(t){return typeof t=="string"&&nr.includes(t)}function an(){try{return globalThis.localStorage??null}catch{return null}}function St(t=an()){try{let e=t?.getItem(wt);return sr(e)?e:"all"}catch{return"all"}}function ln(t,e=an(),r=globalThis.window??null){try{e?.setItem(wt,t)}catch{}r?.dispatchEvent(new CustomEvent(xt,{detail:t}))}function qs(t,{today:e,timeZone:r}){let i=He(e),n=ee(i,6),o=c=>c!==null&&$(c,i)>=0&&$(c,n)<=0;if(o(M(t.status_time,r))||o(M(t.delivered_at,r)))return!0;let a=C(t);return a!==null&&$(a.start,n)<=0&&$(a.end,i)>=0}function cn(t,e,r){switch(e){case"active":return _e(t.status);case"completed":return!_e(t.status);case"recent":return qs(t,r);default:return!0}}function dn(t,e,{today:r}){switch(e){case"active":return!ve(t,r);case"completed":return ve(t,r);case"recent":{let i=He(r);return $(t.day,i)>=0&&$(t.day,ee(i,6))<=0}default:return!0}}var or=class extends oe{static properties={snapshot:{attribute:!1},locale:{attribute:!1},_returnId:{state:!0},_mode:{state:!0}};static styles=[H,xe,x`
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
    `];constructor(){super(),this.snapshot=null,this.locale=Se(void 0),this._returnId=null,this._mode="view"}async open(e,r=null){this._returnId=e,this._mode="view",await this.showDialog(r)}dialogClosed(){this._returnId=null,this._mode="view"}canLightDismiss(){return this._mode==="view"&&!this._busy}get _return(){let e=this._returnId;return e===null?null:this.snapshot?.returns.find(r=>r.id===e)??null}renderContent(){let e=this._return,r=this.snapshot?.settings.today??"";return l`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">
            ${e?ye(e):s.returnDetails}
          </h2>
          ${e?this._renderBadges(e,r):d}
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
          </div>`:d}
      ${e&&!e.restricted&&this.snapshot?.settings.user_is_admin===!0?this._renderActions():d}
    `}_renderBadges(e,r){return l`<div class="dialog-badges">
      <span class="badge return">
        <ha-icon icon=${Ee} aria-hidden="true"></ha-icon>${Ke(e,r)}
      </span>
      ${e.private||e.restricted?l`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${s.private}
          </span>`:d}
      ${e.archived?l`<span class="badge">${s.archived}</span>`:d}
    </div>`}_renderBody(e){return e?this._mode==="remove"?l`<p>${s.removeReturnQuestion}</p>`:l`<p class="hint">${s.returnHint}</p>
      ${this._renderFacts(e)}`:l`<p class="empty">${s.returnNotFound}</p>`}_renderFacts(e){let r=this.locale,i=(m,_)=>l`<div><dt>${m}</dt><dd>${_}</dd></div>`,n=Zt(e.pickup_rule),o=e.restricted?null:R(e),a=e.restricted?null:$t(e.tracking_url),c=e.tracking_number?.trim()??"",u=this._parcels(e);return l`<dl class="facts">
      ${e.pickup?i(s.pickup,l`${D(e.pickup,r)}${n?l`<div class="hint">${n}</div>`:d}`):d}
      ${e.started?i(s.returnStartedDay,A(e.started,r)):d}
      ${o||a?i(s.returnCarrier,l`${o??""}${a?l`<a class="link" href=${a} target="_blank" rel="noopener noreferrer">
                  ${s.trackOnline}<span class="sr-only"> ${s.opensInNewTab}</span>
                  <ha-icon icon="mdi:open-in-new" aria-hidden="true"></ha-icon>
                </a>`:d}`):d}
      ${c?i(s.trackingNumber,c):d}
      ${e.order_numbers.length?i(s.orders,e.order_numbers.join(", ")):d}
      ${e.items.length?i(s.items,l`<ul>
              ${e.items.map(m=>l`<li>${m}</li>`)}
            </ul>`):d}
      ${u.length?i(s.returnSentBackFrom,l`<ul>
              ${u.map(m=>this._renderParcel(m))}
            </ul>`):d}
      ${e.emails.length?i(s.returnEmails,this._renderEmails(e)):d}
    </dl>`}_parcels(e){let r=this.snapshot?.parcels??[];return e.parcel_ids.flatMap(i=>r.find(n=>n.id===i)??[])}_renderParcel(e){let r=P(e),i=e.delivered_undated?s.dateNotKnownInline:e.delivered_at?A(e.delivered_at,this.locale):"",n=[K(e.status),i].filter(Boolean).join(" \xB7 ");return e.restricted?l`<li>${r} · ${n}</li>`:l`<li>
      <button
        type="button"
        class="link-btn"
        aria-haspopup="dialog"
        aria-label=${h(s.showParcel,{name:r})}
        aria-disabled=${this._busy?"true":"false"}
        @click=${()=>this._openParcel(e.id)}
      >
        ${r}</button
      > · ${n}
    </li>`}_renderEmails(e){let r=this.locale;return l`<ul class="emails">
      ${e.emails.map(i=>{let n=i.label.trim(),o=[i.time?A(i.time,r):"",Te(i.source)].filter(Boolean).join(" \xB7 ");return l`<li>
          ${n?l`<div>${n}</div>`:d}
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
    </div>`}_startRemove(){this._mode="remove",this._error=null,this.focusAfterRender("[data-cancel]")}_backToView(){this._mode="view",this._error=null,this.focusAfterRender('[data-mode="remove"]')}_remove(){let e=this.hass,r=this._return;!e||!r||this.runAction(()=>V(e,"return/remove",{return_id:r.id}),()=>this.closeDialog())}_openParcel(e){this._busy||(this.closeDialog(),this.dispatchEvent(new CustomEvent(ri,{detail:e})))}};F("parcels-return-dialog",or);var Vs="parcels/subscribe",un=[2e3,1e4,3e4,6e4,3e5],Rt=new Map,Gs=0;function hn(t,e){try{t(e)}catch(r){console.error(r)}}function pn(t,e){t.state=e;for(let r of[...t.listeners.values()])hn(r,e)}function mn(t){try{t().catch(()=>{})}catch{}}function Ct(t){t.retryTimer!==void 0&&(clearTimeout(t.retryTimer),t.retryTimer=void 0)}function Tt(t){t.connection.removeEventListener("ready",t.onReady),t.connection.removeEventListener("disconnected",t.onDisconnected)}function Ys(t){Ct(t);let e=un[Math.min(t.retries,un.length-1)]??3e5;t.retries+=1,t.retryTimer=setTimeout(()=>{t.retryTimer=void 0,ar(t)},e)}function ar(t){if(t.released||t.unsubscribe||t.pending||t.listeners.size===0)return;Ct(t);let e=++t.attempt,r=t.epoch,i=()=>!t.released&&t.attempt===e;t.pending=!0;let n;try{n=t.connection.subscribeMessage(o=>{i()&&(t.retries=0,pn(t,{snapshot:nn(o),error:null}))},{type:Vs},{resubscribe:!1})}catch(o){n=Promise.reject(o)}n.then(o=>{if(i()){t.pending=!1,t.unsubscribe=o;return}t.epoch===r&&mn(o),t.released&&t.attempt===e+1&&(t.pending=!1,Tt(t))},o=>{i()?(t.pending=!1,pn(t,{snapshot:t.state.snapshot,error:B(o)}),Ys(t)):t.released&&t.attempt===e+1&&(t.pending=!1,Tt(t))})}function Qs(t,e){if(!t.listeners.delete(e)||t.listeners.size>0)return;t.released=!0,t.attempt+=1,Ct(t),Rt.get(t.connection)===t&&Rt.delete(t.connection);let r=t.unsubscribe;t.unsubscribe=null,r&&mn(r),t.pending||Tt(t)}function Zs(t){let e={connection:t,listeners:new Map,state:{snapshot:null,error:null},epoch:0,attempt:0,unsubscribe:null,pending:!1,released:!1,retries:0,retryTimer:void 0,onReady:()=>{e.released||e.unsubscribe||(e.pending=!1,e.retries=0,ar(e))},onDisconnected:()=>{e.epoch+=1,e.attempt+=1,e.unsubscribe=null,e.pending=!1,Ct(e),e.released&&Tt(e)}};return e}function fn(t,e){let r=++Gs,i=Rt.get(t);i?(i.listeners.set(r,e),(i.state.snapshot||i.state.error)&&hn(e,i.state)):(i=Zs(t),Rt.set(t,i),i.listeners.set(r,e),t.addEventListener("ready",i.onReady),t.addEventListener("disconnected",i.onDisconnected),ar(i));let n=i,o=!0;return()=>{o&&(o=!1,Qs(n,r))}}var Et=class{snapshot=null;error=null;_host;_connection=null;_unsubscribe=null;_hostConnected=!1;constructor(e){this._host=e,e.addController(this)}setConnection(e){e!==this._connection&&(this._release(),this._connection=e,this.snapshot=null,this.error=null,this._hostConnected&&this._subscribe(),this._host.requestUpdate())}hostConnected(){this._hostConnected=!0,this._subscribe()}hostDisconnected(){this._hostConnected=!1,this._release()}_subscribe(){!this._connection||this._unsubscribe||(this._unsubscribe=fn(this._connection,e=>{this.snapshot=e.snapshot??this.snapshot,this.error=e.error,this._host.requestUpdate()}))}_release(){let e=this._unsubscribe;this._unsubscribe=null,e?.()}};var qe=class extends W{static properties={_actionError:{state:!0}};_snapshots=new Et(this);_hass=void 0;_hassKey=null;_locale=null;_localeKey="";constructor(){super(),this._actionError=null}get hass(){return this._hass}set hass(e){this._hass=e,this._snapshots.setConnection(e?.connection??null),this.toggleAttribute("dark",e?.themes?.darkMode===!0);let r=JSON.stringify([e?.language,e?.locale?.language,e?.locale?.time_format,e?.locale?.time_zone,e?.config?.time_zone,e?.user?.is_admin,e?.themes?.darkMode]);r!==this._hassKey&&(this._hassKey=r,this.requestUpdate()),this.hassChanged()}hassChanged(){}get snapshot(){return this._snapshots.snapshot}get locale(){let e=this._snapshots.snapshot?.settings.time_zone,r=`${this._hassKey??""}|${e??""}`;return(!this._locale||r!==this._localeKey)&&(this._locale=Se(this._hass,e),this._localeKey=r),this._locale}async callService(e,r,i){let n=this._hass;if(!n)return!1;this._actionError=null;try{return await ne(n,e,r),!0}catch(o){return this._actionError=h(i,{message:B(o)}),!1}}renderBanners(){let{snapshot:e,error:r}=this._snapshots;return!r&&!this._actionError?d:l`<div class="banners">
      ${r?l`<div class="alert ${e?"warning":"error"}" role="alert">
            <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              ${h(e?s.refreshError:s.loadError,{message:r})}
            </span>
          </div>`:d}
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
          </div>`:d}
    </div>`}renderLoading(){return this._snapshots.error?d:l`<p class="empty" role="status">${s.loading}</p>`}showActionError(e){this._actionError=e}_dismissActionError(){this._actionError=null}},Ae=class extends qe{static properties={_busyParcels:{state:!0},_filter:{state:!0}};_focusedParcel=null;_focusedReturn=null;constructor(){super(),this._busyParcels=new Set,this._filter=St()}connectedCallback(){super.connectedCallback(),this._filter=St(),window.addEventListener(xt,this._onFilterEvent),window.addEventListener("storage",this._onStorage)}disconnectedCallback(){super.disconnectedCallback(),window.removeEventListener(xt,this._onFilterEvent),window.removeEventListener("storage",this._onStorage)}setFilter(e){this._filter=e,ln(e)}filterParcels(e,r){let i=this._filter;if(i==="all")return r;let n={today:e.settings.today,timeZone:e.settings.time_zone};return r.filter(o=>cn(o,i,n))}filterReturns(e,r){let i=this._filter;if(i==="all")return r;let n={today:e.settings.today};return r.filter(o=>dn(o,i,n))}_candidates=null;possiblyFor(e){let r=this.snapshot;if(!r)return null;this._candidates?.snapshot!==r&&(this._candidates={snapshot:r,map:Ii(r.merge_suggestions)});let i=this._candidates.map,n=new Set(e.map(a=>a.id)),o=new Map;for(let a of e)for(let c of i.get(a.id)??[])n.has(c.id)||o.set(c.id,c);return o.size?zi([...o.values()]):null}_onFilterEvent=e=>{let r=e.detail;sr(r)&&(this._filter=r)};_onStorage=e=>{(e.key===null||e.key===wt)&&(this._filter=St())};willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement,i=r instanceof HTMLElement?r.closest(".chip"):null;this._focusedParcel=i?.dataset.parcelId??null,this._focusedReturn=i?.dataset.returnId??null}updated(e){super.updated(e);let r=this._focusedParcel,i=this._focusedReturn;if(this._focusedParcel=null,this._focusedReturn=null,this.shadowRoot?.activeElement||!lr())return;let n=r!==null?Xt(r):i!==null?er(i):null;n&&this.renderRoot.querySelector(n)?.focus()}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback], button.chip-main")}openDetails=(e,r)=>{this.renderRoot.querySelector("parcels-details-dialog")?.open(e.id,()=>{(r.isConnected?r:this.renderRoot.querySelector(Xt(e.id))??this.focusFallback())?.focus()})};openReturn=(e,r)=>{this.renderRoot.querySelector("parcels-return-dialog")?.open(e.id,()=>{(r.isConnected?r:this.renderRoot.querySelector(er(e.id))??this.focusFallback())?.focus()})};undoMerge=e=>{this._parcelAction(e.id,"undo_merge",{parcel_id:e.id},s.undoFailed)};keepMerge=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_merge:!0},s.keepFailed)};undoInferred=e=>{this._parcelAction(e.id,"undo_delivery",{parcel_id:e.id},s.undoInferredFailed)};keepInferred=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_delivery:!0},s.keepInferredFailed)};renderDetailsDialog(){return l`<parcels-details-dialog
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
    ></parcels-return-dialog>`}_opener(){let e=this.shadowRoot?.activeElement;return e instanceof HTMLElement?e:this.focusFallback()}_onOpenParcel(e){let r=this.snapshot?.parcels.find(n=>n.id===e.detail),i=this._opener();r&&i&&this.openDetails(r,i)}_onOpenReturn(e){let r=this.snapshot?.returns.find(n=>n.id===e.detail),i=this._opener();r&&i&&this.openReturn(r,i)}async _parcelAction(e,r,i,n){if(!this._busyParcels.has(e)){this._busyParcels=new Set([...this._busyParcels,e]);try{await this.callService(r,i,n)}finally{let o=new Set(this._busyParcels);o.delete(e),this._busyParcels=o}}}_onDialogError(e){this.showActionError(e.detail)}};function lr(){let t=document.activeElement;return!t||t===document.body}function cr(t){if(typeof t!="object"||t===null||Array.isArray(t))throw new Error(s.configInvalid);return t}function dr(t){let e=t.title;if(e!=null){if(typeof e!="string")throw new Error(s.configTitle);return e.trim()}}function ur(t){return typeof t.type=="string"?t.type:""}function pr(t){let e=cr(t),r=e.show_archived??!0;if(typeof r!="boolean")throw new Error(s.configShowArchived);return{type:ur(e),title:dr(e),show_archived:r}}function hr(t){let e=cr(t);return{type:ur(e),title:dr(e)}}function mr(t){let e=cr(t);return{type:ur(e),title:dr(e)}}function Pe(t,e){return t===void 0?e:t||null}function Js(t,e){let r=M(t.status_time,e.timeZone);switch(t.status){case"cancelled":return null;case"delivered":{let n=M(t.delivered_at,e.timeZone)??r;return n?{kind:"delivered",from:n,to:n}:null}case"returned":return r?{kind:"returned",from:r,to:r}:null;case"ready_for_pickup":{let n=r??e.today;return{kind:"pickup",from:n,to:oi(n,e.today)}}default:break}let i=C(t);return i?{kind:"eta",from:i.start,to:i.end}:(t.status==="attempted"||t.status==="exception")&&r?{kind:"status",from:r,to:r}:null}function fr(t){return t.type==="parcel"?t.parcel.id:`return:${t.ret.id}`}function gn(t){return t.window_start??t.window_end??"~"}function Ve(t,e){return t<e?-1:t>e?1:0}function Xs(t,e){return Ve(gn(t.parcel),gn(e.parcel))||Ve(P(t.parcel).toLowerCase(),P(e.parcel).toLowerCase())||Ve(t.parcel.id,e.parcel.id)}function eo(t,e){return Ve(ye(t.ret).toLowerCase(),ye(e.ret).toLowerCase())||Ve(t.ret.id,e.ret.id)}function to(t,e){let r=t.startCol-e.startCol||e.endCol-e.startCol-(t.endCol-t.startCol)||(t.type===e.type?0:t.type==="parcel"?-1:1);return r||(t.type==="parcel"&&e.type==="parcel"?Xs(t,e):t.type==="return"&&e.type==="return"?eo(t,e):0)}function _n(t,e,r,i,n=[]){let o=si(e),a=ee(e,6),c=[];for(let p of t){if(p.archived&&!i.showArchived)continue;let g=Js(p,r);!g||$(g.to,e)<0||$(g.from,a)>0||c.push({type:"parcel",parcel:p,members:[p],placement:g,startCol:Math.max(0,ae(e,g.from)),endCol:Math.min(6,ae(e,g.to)),continuesBefore:$(g.from,e)<0,continuesAfter:$(g.to,a)>0,lane:0})}let u=Yt(c,p=>Qt(p.parcel,p.placement.kind,p.placement.from,p.placement.to)).map(p=>({...p.reduce((f,v)=>Ce(v.parcel,f.parcel)<0?v:f),members:p.map(f=>f.parcel).sort(Ce)}));for(let p of n){if(p.archived&&!i.showArchived||$(p.day,e)<0||$(p.day,a)>0)continue;let g=ae(e,p.day);u.push({type:"return",ret:p,day:p.day,startCol:g,endCol:g,continuesBefore:!1,continuesAfter:!1,lane:0})}u.sort(to);let m=[];for(let p of u){let g=m.findIndex(f=>f<p.startCol);g===-1&&(g=m.length),m[g]=p.endCol,p.lane=g}let _=o.map((p,g)=>u.filter(f=>f.startCol<=g&&g<=f.endCol).sort((f,v)=>f.lane-v.lane));return{start:e,end:a,days:o,items:u,lanes:m.length,perDay:_,busy:_.map(p=>p.length>0)}}var ro=600,io=616,no={weekday:"short"},so={day:"numeric"},oo={weekday:"long",day:"numeric",month:"long"},ao={weekday:"long",day:"numeric",month:"short"},gr=class extends Ae{static properties={_config:{state:!0},_weekOffset:{state:!0},_narrow:{state:!0},_refreshing:{state:!0}};static styles=[H,ut,x`
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
    `];_resizeObserver=null;_resizeFrame=0;_layoutCache=null;constructor(){super(),this._config=pr({}),this._weekOffset=0,this._narrow=!1,this._refreshing=!1}static getStubConfig(){return{}}setConfig(e){this._config=pr(e)}getCardSize(){let e=this._layout();return e?this._narrow?9+e.perDay.reduce((i,n)=>i+n.length,0):3+Math.max(1,e.lanes):4}getGridOptions(){return{columns:"full",rows:"auto",min_columns:6}}connectedCallback(){super.connectedCallback(),typeof ResizeObserver<"u"&&(this._resizeObserver??=new ResizeObserver(e=>{let r=e[e.length-1]?.contentRect.width??0;cancelAnimationFrame(this._resizeFrame),this._resizeFrame=requestAnimationFrame(()=>this._measure(r))}),this._resizeObserver.observe(this))}disconnectedCallback(){super.disconnectedCallback(),this._resizeObserver?.disconnect(),cancelAnimationFrame(this._resizeFrame)}firstUpdated(e){super.firstUpdated(e),this._measure(this.getBoundingClientRect().width)}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback]")}_measure(e){e<=0||(e<ro?this._narrow=!0:e>=io&&(this._narrow=!1))}_monday(e){return ee(He(e.settings.today),7*this._weekOffset)}_layout(){let e=this.snapshot;if(!e)return null;let r=this._monday(e),i=this._config.show_archived,n=this._filter,o=this._layoutCache;if(o&&o.snapshot===e&&o.monday===r&&o.showArchived===i&&o.filter===n)return o.layout;let a=_n(this.filterParcels(e,e.parcels),r,{today:e.settings.today,timeZone:e.settings.time_zone},{showArchived:i},this.filterReturns(e,e.returns));return this._layoutCache={snapshot:e,monday:r,showArchived:i,filter:n,layout:a},a}render(){let e=this.snapshot,r=this._layout(),i=Pe(this._config.title,s.defaultWeekTitle),n=r?U(r.start,r.end,this.locale,gi):"";return l`<ha-card>
        <div class="header">
          <div class="heading">
            ${i?l`<h2 class="title">${i}</h2>`:d}
            ${n?l`<p class="range" aria-live="polite">${n}</p>`:d}
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
      aria-label=${h(s.weekOf,{range:i})}
      style=${N(u)}
    >
      ${r.days.map((m,_)=>l`<div
            class="day-bg ${m===o?"today":""}"
            style=${N({"grid-column":String(_+1)})}
            aria-hidden="true"
          ></div>`)}
      ${r.days.map((m,_)=>l`<div
            class="day-head ${m===o?"today":""}"
            style=${N({"grid-column":String(_+1)})}
            aria-current=${m===o?"date":d}
          >
            <span class="dow" aria-hidden="true">${D(m,n,no)}</span>
            <span class="dom" aria-hidden="true">${D(m,n,so)}</span>
            <span class="sr-only">${D(m,n,oo)}</span>
          </div>`)}
      ${a?l`<p class="week-empty">${this._emptyText()}</p>`:d}
      ${X(r.items,fr,m=>this._chip(m,!1,{"grid-column":`${m.startCol+1} / ${m.endCol+2}`,"grid-row":String(m.lane+2)}))}
    </div>`}_renderStacked(e,r,i){let n=this.locale,o=e.settings.today,a=this._filter!=="all"&&r.items.length===0;return l`${a?l`<p class="week-empty stacked">${this._emptyText()}</p>`:d}
      <ol class="days" aria-label=${h(s.weekOf,{range:i})}>
      ${r.days.map((c,u)=>{let m=r.perDay[u]??[],_=c===o;return l`<li
          class="day ${m.length?"":"compact"} ${_?"today":""}"
          aria-current=${_?"date":d}
        >
          <p class="day-label">
            ${D(c,n,ao)}${_?l`<span class="badge info">${s.todayTag}</span>`:d}
          </p>
          ${m.length?l`<ul class="day-chips">
                ${X(m,fr,p=>l`<li>${this._chip(p,!0,void 0,u)}</li>`)}
              </ul>`:l`<span class="muted">${s.noDeliveriesThisDay}</span>`}
        </li>`})}
    </ol>`}_chip(e,r,i,n){if(e.type==="return")return en(e.ret,{locale:this.locale,today:this.snapshot?.settings.today??"",position:i,onOpen:this.openReturn});let o=e.continuesBefore&&(!r||n===e.startCol),a=e.continuesAfter&&(!r||n===e.endCol);return _t(e.parcel,{locale:this.locale,placement:e.placement,continuesBefore:o,continuesAfter:a,showRange:r,members:e.members,possibly:this.possiblyFor(e.members),busy:e.members.some(c=>this._busyParcels.has(c.id)),position:i,onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge,onUndoInferred:this.undoInferred,onKeepInferred:this.keepInferred})}_renderFilters(){return l`<div class="filters" role="group" aria-label=${s.filterLabel}>
      ${nr.map(e=>l`<button
            type="button"
            class="filter-btn"
            aria-pressed=${this._filter===e?"true":"false"}
            title=${e==="recent"?s.filterRecentHint:d}
            @click=${()=>this.setFilter(e)}
          >
            ${kt[e]}
          </button>`)}
    </div>`}_emptyText(){return this._filter==="all"?s.noDeliveriesThisWeek:s.filterEmptyWeek}_previousWeek(){this._weekOffset-=1}_nextWeek(){this._weekOffset+=1}_thisWeek(){this._weekOffset=0}async _refresh(){if(!this._refreshing){this._refreshing=!0;try{await this.callService("refresh",{},s.refreshFailed)}finally{this._refreshing=!1}}}_openAdd(e){let r=e.currentTarget;this.renderRoot.querySelector("parcels-add-dialog")?.open(()=>{r.isConnected&&r.focus()})}_onAddError(e){this.showActionError(e.detail)}};F("parcels-week-card",gr);we("parcels-week-card",s.weekCardName,s.weekCardDescription);var _r=class extends Ae{static properties={_config:{state:!0}};static styles=[H,ut,x`
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
    `];_listCache=null;constructor(){super(),this._config=hr({})}static getStubConfig(){return{}}setConfig(e){this._config=hr(e)}getCardSize(){let e=this._list()?.boxes;return e?1+Math.max(1,e.length):3}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}focusFallback(){return this.renderRoot.querySelector("button.chip-main")??this.renderRoot.querySelector(".content")}_list(){let e=this.snapshot;if(!e)return null;let r=this._filter,i=this._listCache;if(i?.snapshot===e&&i.filter===r)return i;let n=Ei(e.parcels),o=this.filterParcels(e,n);return this._listCache={snapshot:e,filter:r,boxes:Ki(o),hidden:n.length-o.length},this._listCache}render(){let e=this._list(),r=Pe(this._config.title,s.defaultListTitle);return l`<ha-card>
        ${r?l`<div class="header"><h2 class="title">${r}</h2></div>`:d}
        ${this.renderBanners()}
        <div class="content" tabindex="-1">
          ${e?this._renderList(e.boxes,e.hidden):this.renderLoading()}
        </div>
      </ha-card>
      ${this.renderDetailsDialog()} ${this.renderReturnDialog()}`}_renderFilterNote(e){return e===0||this._filter==="all"?d:l`<p class="filter-note">
      ${h(s.filterNote,{filter:kt[this._filter]})} ·
      <button type="button" class="link-btn" @click=${this._showAll}>${s.filterShowAll}</button>
    </p>`}_showAll=()=>{this.setFilter("all")};_renderList(e,r){if(!e.length)return l`${this._renderFilterNote(r)}
        <p class="empty">${r>0?s.noUndatedMatch:s.noUndatedParcels}</p>`;let i=this.locale;return l`${this._renderFilterNote(r)}
      <ul class="list">
      ${X(e,n=>n.parcel.id,({parcel:n,members:o})=>l`<li>
            ${_t(n,{locale:i,showStatus:!0,members:o,possibly:this.possiblyFor(o),busy:o.some(a=>this._busyParcels.has(a.id)),onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge,onUndoInferred:this.undoInferred,onKeepInferred:this.keepInferred})}
          </li>`)}
    </ul>`}};F("parcels-list-card",_r);we("parcels-list-card",s.listCardName,s.listCardDescription);function lo(t,e,r){let i=t.get(e);return i==="pending"||i!==void 0&&i===r}function At(t,e,r){if(!e.size)return t;let i=t.filter(n=>!lo(e,n.id,r));return i.length===t.length?t:i}function vr(t,e){let r=new Map(t);for(let i of e)r.set(i,"pending");return r}function yr(t,e){let r=new Map(t);for(let i of e)r.delete(i);return r}function $r(t,e,r,i){let n=new Map(t);for(let o of e)r&&i(o)?n.set(o,r):n.delete(o);return n}function bn(t,e){let r=null;for(let[i,n]of t)n!=="pending"&&n!==e&&(r??=new Map(t),r.delete(i));return r??t}function vn(t,e){if(t<=0)return null;let r=t===1?s.aiQueueOne:h(s.aiQueueMany,{count:t});if(e===null)return r;let i=Math.max(1,Math.round(e/60));return i<120?h(s.aiQueueMinutes,{queue:r,minutes:i}):h(s.aiQueueHours,{queue:r,hours:Math.round(i/60)})}function br(t,e,r){return t<=0?null:t===1?e:h(r,{count:t})}function yn(t){let e=[br(t.added,s.trustAddedOne,s.trustAddedMany),br(t.rechecking,s.trustRecheckOne,s.trustRecheckMany),br(t.kept,s.trustKeptOne,s.trustKeptMany)].filter(r=>r!==null);return e.length?h(s.trustDoneWith,{domain:t.domain,parts:e.join(", ")}):h(s.trustDone,{domain:t.domain})}function $n(t){let e=[[s.checkHeaders,String(t.headers)]];return t.servers.length&&e.push([s.checkServers,t.servers.map(r=>r||s.checkNoServer).join(", ")]),t.originals>0&&e.push([s.checkOriginals,String(t.originals)]),t.used===null?(e.push([s.checkUsed,s.checkUsedNone]),e):(e.push([s.checkUsed,h(s.checkUsedHeader,{n:t.used+1})],["DKIM",t.dkim||s.checkNoResult],["DMARC",t.dmarc||s.checkNoResult],["SPF",t.spf||s.checkNoResult]),e)}var Ie=["review","filtered"],co=new Set(["not_parcel","unknown"]),uo={weekday:"short",day:"numeric",month:"short"};function kn(t){return G(t.received??t.created)??-1/0}function wn(t){return[...t].sort((e,r)=>kn(r)-kn(e)||(e.id<r.id?-1:e.id>r.id?1:0))}function po(t){return[...t].sort((e,r)=>(r.day??"").localeCompare(e.day??"")||(e.id<r.id?-1:e.id>r.id?1:0))}function kr(t,e){if(!t.has(e))return t;let r=new Map(t);return r.delete(e),r}var wr=class extends qe{static properties={_config:{state:!0},_tab:{state:!0},_editing:{state:!0},_editForm:{state:!0},_editProblem:{state:!0},_busyItems:{state:!0},_itemErrors:{state:!0},_hidden:{state:!0},_confirmClearAll:{state:!0},_confirmTrust:{state:!0},_trustStatus:{state:!0}};static styles=[H,x`
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
    `];connectedWhileHidden=!0;_focusedItem=null;_listCache=null;_visibleCache=null;_clearingAll=!1;constructor(){super(),this._config=mr({}),this._tab="review",this._editing=null,this._editForm=Bt(null),this._editProblem=null,this._busyItems=new Set,this._itemErrors=new Map,this._hidden=new Map,this._confirmClearAll=!1,this._confirmTrust=null,this._trustStatus=null}static getStubConfig(){return{}}setConfig(e){this._config=mr(e)}getCardSize(){if(!this._visible())return 0;let e=this._visibleLists();if(!e)return 3;let r=this._tab==="review"?e.review.length+e.suggestions.length:e.filtered.length;return 2+2*Math.max(1,r)}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}hassChanged(){this._syncVisibility()}_visible(){let e=this.snapshot;return e?e.settings.user_is_admin:this.hass?.user?.is_admin===!0}_syncVisibility(){let e=!this._visible();this.hidden!==e&&(this.hidden=e,this.dispatchEvent(new CustomEvent("card-visibility-changed",{bubbles:!0,composed:!0,detail:{value:!e}})))}_lists(){let e=this.snapshot;return e?(this._listCache?.snapshot!==e&&(this._listCache={snapshot:e,review:wn(e.review),suggestions:po(e.merge_suggestions),filtered:wn(e.filtered)}),this._listCache):null}_visibleLists(){let e=this._lists();if(!e)return null;let r=this._hidden;if(this._visibleCache?.lists!==e||this._visibleCache.hidden!==r){let i=this.snapshot;this._visibleCache={lists:e,hidden:r,visible:{review:At(e.review,r,i),suggestions:At(e.suggestions,r,i),filtered:At(e.filtered,r,i)}}}return this._visibleCache.visible}_listed(e){let r=this._lists();return r?[...r.review,...r.suggestions,...r.filtered].some(i=>i.id===e):!1}willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement,i=r instanceof HTMLElement?r.closest("[data-item-id]"):null;if(i){let o=[...this.renderRoot.querySelectorAll("[data-item-id]")].filter(a=>!a.closest("[hidden]"));this._focusedItem={id:i.dataset.itemId??"",index:o.indexOf(i)}}else this._focusedItem=null;this._hidden=bn(this._hidden,this.snapshot),this._confirmClearAll&&!this._visibleLists()?.filtered.length&&(this._confirmClearAll=!1,r instanceof HTMLElement&&r.closest(".confirm")&&this._focusAfterUpdate("#panel-filtered"));let n=this._lists();if(n){let o=new Set([...n.review,...n.suggestions,...n.filtered].map(a=>a.id));this._editing!==null&&!o.has(this._editing)&&(this._editing=null,this._editProblem=null);for(let a of this._itemErrors.keys())o.has(a)||(this._itemErrors=kr(this._itemErrors,a))}}updated(e){super.updated(e),this._syncVisibility();let r=this._focusedItem;if(this._focusedItem=null,!r||this.shadowRoot?.activeElement||!lr())return;let n=[...this.renderRoot.querySelector(`#panel-${this._tab}`)?.querySelectorAll("[data-item-id]")??[]];(n.find(a=>a.dataset.itemId===r.id)??n[Math.min(Math.max(r.index,0),n.length-1)]??this.renderRoot.querySelector(`#tab-${this._tab}`))?.focus()}render(){if(!this._visible())return d;let e=this._visibleLists(),r=Pe(this._config.title,s.defaultReviewTitle);return l`<ha-card>
      ${r?l`<div class="header"><h2 class="title">${r}</h2></div>`:d}
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
    </ha-card>`}_renderTabs(e,r){let i=n=>h(s.tabCount,{label:n==="review"?s.tabReview:s.tabFiltered,count:n==="review"?e:r});return l`<div
      class="tabs"
      role="tablist"
      aria-label=${s.reviewTabs}
      @keydown=${this._onTabKeyDown}
    >
      ${Ie.map(n=>{let o=this._tab===n;return l`<button
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
    </div>`}_renderReviewList(e,r){let i=this.snapshot?.settings,n=i?vn(i.ai_queue,i.ai_queue_seconds):null,o=n?l`<p class="hint queue-hint">${n}</p>`:d,a=l`<div class="trust-status" role="status">
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
          </div>`:d}
    </div>`;return!e.length&&!r.length?l`${a}${o}<p class="empty">${s.emptyReview}</p>`:l`${a}${o}<div class="items">
      ${X(r,c=>c.id,(c,u)=>this._renderMergeSuggestion(c,u))}
      ${X(e,c=>c.id,(c,u)=>this._renderReviewItem(c,u))}
    </div>`}_renderMergeSuggestion(e,r){let i=this.locale,o=this._busyItems.has(e.id)?"true":"false",a=`suggestion-subject-${r}`,c=je(e.parcel,i),u=ht(e.reason),m=this.snapshot?.settings,_=m?[...e.candidates].sort(Vt(e.parcel,{today:m.today,timeZone:m.time_zone})):e.candidates;return l`<article
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
        ${h(s.suggestionTitle,{parcel:be(e.parcel,i).title})}
      </h3>
      <p class="subject-lines">${this._renderLines(e.parcel)}</p>
      ${u?l`<p class="meta">${h(s.reasonIs,{reason:u})}</p>`:d}
      <p class="hint">${s.suggestionHint}</p>
      <ul class="candidates">
        ${_.map(p=>{let g=je(p,i);return l`<li class="candidate">
            <span class="grow">${this._renderLines(p)}</span>
            <button
              type="button"
              class="btn"
              aria-label=${h(s.mergeSuggestedLabel,{candidate:g,title:c})}
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
          aria-label=${h(s.keepApartLabel,{title:c})}
          aria-disabled=${o}
          @click=${()=>this._command(e.id,"suggestion/dismiss",{suggestion_id:e.id})}
        >
          ${s.keepApart}
        </button>
      </div>
    </article>`}_renderLines(e){let r=be(e,this.locale);return l`<span class="block"><strong>${r.title}</strong> · ${r.when}</span>
      <span class="meta block">${r.carrier}</span>
      <span class="meta block items-line">${r.items??s.itemsNotKnown}</span>`}_renderFilteredList(e){return l`<p class="hint filtered-hint">${s.filteredHint}</p>
      ${e.length?l`${this._renderClearAll()}
            <div class="items">
            ${X(e,r=>r.id,(r,i)=>this._renderFilteredItem(r,i))}
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
      </div>`}_renderHead(e,r,i=d){return l`<div class="item-head">
        <span class="sender">${e.sender||e.sender_domain}</span>${i}
      </div>
      <h3 class="subject" id=${r}>${e.subject.trim()||s.noSubject}</h3>`}_renderError(e){let r=this._itemErrors.get(e);return r?l`<div class="alert error" role="alert">
          <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
          <span class="grow">${r}</span>
        </div>`:d}_renderReviewItem(e,r){let i=this.locale,n=this._busyItems.has(e.id),o=this._editing===e.id,a=`review-subject-${r}`,c=e.received??e.created,u=$i(e.reason),m=[c?h(s.receivedOn,{date:A(c,i)}):"",e.mailbox_owner?h(s.mailboxOf,{owner:e.mailbox_owner}):"",u?h(s.reasonIs,{reason:u}):""].filter(Boolean),_=e.source==="ai"?l`<span class="badge ai" title=${s.aiSuggestionLabel}>
            ${s.aiBadge}<span class="sr-only">, ${s.aiSuggestionLabel}</span>
          </span>`:d;return l`<article
      class="item"
      tabindex="-1"
      data-item-id=${e.id}
      aria-labelledby=${a}
      aria-busy=${n?"true":"false"}
    >
      ${this._renderHead(e,a,_)}
      ${m.length?l`<p class="meta">${m.join(" \xB7 ")}</p>`:d}
      ${e.authenticated?d:l`<div class="alert warning">
            <ha-icon icon="mdi:shield-alert-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              <strong class="block">${s.unverifiedSender}</strong>
              ${e.trusted_sender?h(s.trustedSenderNote,{domain:e.sender_domain||e.sender}):s.unverifiedSenderHint}
            </span>
          </div>`}
      ${e.checks?this._renderChecks(e.checks):d}
      ${e.errors.length?this._renderFailedChecks(e.errors):d}
      ${o?this._renderEditForm(e,n):this._renderSuggestion(e.suggestion)}
      ${this._renderError(e.id)} ${o?d:this._renderReviewActions(e,n)}
    </article>`}_renderChecks(e){return l`<details class="checks">
      <summary>${s.senderChecks}</summary>
      <dl class="facts">
        ${$n(e).map(([r,i])=>l`<dt>${r}</dt><dd>${i}</dd>`)}
      </dl>
    </details>`}_renderFailedChecks(e){return l`<details class="checks">
      <summary>${s.failedChecks}</summary>
      <ul class="codes">
        ${e.map(r=>l`<li><code>${r}</code></li>`)}
      </ul>
    </details>`}_renderSuggestion(e){if(!e)return l`<p class="hint section-label">${s.noSuggestion}</p>`;let r=this.locale,i=C(e),n=[[s.fieldKind,Wt(e.kind)||null],[s.fieldMerchant,e.merchant],[s.fieldCarrier,R({carrier:e.carrier,carrier_name:null})],[s.fieldTrackingNumbers,e.tracking_numbers.join(", ")||null],[s.fieldOrderNumbers,e.order_numbers.join(", ")||null],[s.fieldReference,e.reference],[e.kind==="customer_return"?s.pickup:s.expected,i?U(i.start,i.end,r,uo):null],[s.timeWindow,Re(e.window_start,e.window_end,r)],[s.pickupPoint,e.pickup_point],[s.pickupCode,e.pickup_code],[s.items,e.items.length?l`<ul>
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
          </button>`:d}
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
      ${e.trusted_sender||e.fill?d:l`<button
            type="button"
            class="btn"
            data-trust
            title=${h(s.trustSenderHint,{domain:n})}
            aria-disabled=${i}
            aria-expanded=${e.authenticated?d:this._confirmTrust===e.id?"true":"false"}
            @click=${()=>this._askTrust(e)}
          >
            ${s.trustSender}
          </button>`}
      <button
        type="button"
        class="btn danger"
        title=${h(s.ignoreSenderHint,{domain:n})}
        aria-disabled=${i}
        @click=${()=>this._command(e.id,"review/ignore_sender",{review_id:e.id})}
      >
        ${s.ignoreSender}
      </button>
    </div>
    ${this._confirmTrust===e.id?this._renderTrustConfirm(e,n,r):d}`}_renderTrustConfirm(e,r,i){let n=`trust-question-${e.id}`;return l`<div
      class="confirm"
      role="group"
      aria-labelledby=${n}
      @keydown=${o=>this._onTrustKeyDown(o,e.id)}
    >
      <p id=${n}>${h(s.trustQuestion,{domain:r})}</p>
      <div class="row-actions">
        <button
          type="button"
          class="btn danger primary"
          aria-disabled=${i?"true":"false"}
          @click=${()=>{this._trust(e)}}
        >
          ${h(s.trustConfirm,{domain:r})}
        </button>
        <button type="button" class="btn" data-trust-cancel @click=${()=>this._cancelTrust(e.id)}>
          ${s.cancel}
        </button>
      </div>
    </div>`}_renderEditForm(e,r){let i=this._editForm,n=this._editProblem,o=Object.keys(ot).filter(u=>!co.has(u)||u===i.kind);o.includes(i.kind)||o.unshift(i.kind);let a=st();i.carrier&&!Object.hasOwn(se,i.carrier)&&a.unshift({id:i.carrier,name:i.carrier});let c=(u,m,_="text",p)=>{let g=n?.field===u,f=[g?"edit-error":"",p??""].filter(Boolean).join(" ");return l`<label class="field">
        <span class="field-label">${m}</span>
        <input
          type=${_}
          name=${u}
          autocomplete="off"
          .value=${L(i[u])}
          aria-invalid=${g?"true":"false"}
          aria-describedby=${f||d}
          @input=${this._onEditInput}
        />
      </label>`};return l`<form id="edit-form" class="edit-form" novalidate @submit=${this._submitEdit}>
      <div class="form-grid">
        <label class="field">
          <span class="field-label">${s.fieldKind}</span>
          <select name="kind" data-first @change=${this._onEditInput}>
            ${o.map(u=>l`<option value=${u} ?selected=${u===i.kind}>
                  ${Wt(u)||u}
                </option>`)}
          </select>
        </label>
        ${c("merchant",s.fieldMerchant)}
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
            .value=${L(i.items)}
            aria-describedby="edit-hint-items"
            @input=${this._onEditInput}
          ></textarea>
          <span class="hint" id="edit-hint-items">${s.hintItems}</span>
        </label>
      </div>
      ${n?l`<div class="alert error" id="edit-error" role="alert">
            <span class="grow">${n.message}</span>
          </div>`:d}
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
            ${h(s.receivedOn,{date:A(n,this.locale)})}
          </p>`:d}
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
    </article>`}_selectTab(e,r){this._tab=e,r&&this.updateComplete.then(()=>this.renderRoot.querySelector(`#tab-${e}`)?.focus())}_onTabClick(e){let r=e.currentTarget.dataset.tab;this._selectTab(r,!1)}_onTabKeyDown(e){let r=Ie.indexOf(this._tab),i=getComputedStyle(e.currentTarget).direction==="rtl",n;switch(e.key){case"ArrowRight":n=r+(i?-1:1);break;case"ArrowLeft":n=r+(i?1:-1);break;case"Home":n=0;break;case"End":n=Ie.length-1;break;default:return}e.preventDefault();let o=Ie[(n+Ie.length)%Ie.length];o&&this._selectTab(o,!0)}_focusAfterUpdate(e){this.updateComplete.then(()=>this.renderRoot.querySelector(e)?.focus())}_askClearAll(){this._confirmClearAll=!0,this._focusAfterUpdate("#clear-all-cancel")}_cancelClearAll(){this._confirmClearAll=!1,this._focusAfterUpdate("#clear-all")}_onConfirmKeyDown(e){e.key==="Escape"&&(e.preventDefault(),e.stopPropagation(),this._cancelClearAll())}async _clearAll(){let e=this.hass,r=this._visibleLists()?.filtered.map(i=>i.id)??[];if(!(!e||this._clearingAll||!r.length)){this._clearingAll=!0,this._confirmClearAll=!1,this._hidden=vr(this._hidden,r),this._focusAfterUpdate("#panel-filtered");try{await V(e,"filtered/clear_all"),this._hidden=$r(this._hidden,r,this.snapshot,i=>this._listed(i))}catch(i){this._hidden=yr(this._hidden,r),this.showActionError(h(s.actionFailed,{message:B(i)}))}finally{this._clearingAll=!1}}}_focusInItem(e,r){this.updateComplete.then(()=>{let i=this.renderRoot.querySelector(`[data-item-id="${CSS.escape(e)}"]`);(i?.querySelector(r)??i)?.focus()})}_startEdit(e){this._busyItems.has(e.id)||(this._editing=e.id,this._editForm=Bt(e.suggestion),this._editProblem=null,this._itemErrors=kr(this._itemErrors,e.id),this._focusInItem(e.id,"[data-first]"))}_cancelEdit(e){this._editing=null,this._editProblem=null,this._focusInItem(e,"[data-edit]")}_onEditInput(e){let r=e.currentTarget,i=r.name;this._editForm={...this._editForm,[i]:r.value},this._editProblem=null}_submitEdit(e){e.preventDefault();let r=this._editing;if(r===null||this._busyItems.has(r))return;let i=dt(this._editForm);if(i){this._editProblem=i,this._focusInItem(r,`[name="${i.field}"]`);return}this._command(r,"review/accept",{review_id:r,overrides:ui(this._editForm)},{onSuccess:()=>{this._editing===r&&(this._editing=null)}})}_accept(e){this._command(e.id,"review/accept",{review_id:e.id})}_askTrust(e){if(!this._busyItems.has(e.id)){if(e.authenticated){this._trust(e);return}this._confirmTrust=e.id,this._focusInItem(e.id,"[data-trust-cancel]")}}_cancelTrust(e){this._confirmTrust=null,this._focusInItem(e,"[data-trust]")}_onTrustKeyDown(e,r){e.key==="Escape"&&(e.preventDefault(),e.stopPropagation(),this._cancelTrust(r))}async _trust(e){let r=e.sender_domain||e.sender;this._confirmTrust=null,this._trustStatus=null,this._focusInItem(e.id,"[data-trust]"),await this._command(e.id,"review/trust_sender",{review_id:e.id},{hide:!1,onSuccess:i=>{let n=i??{};this._trustStatus=yn({domain:n.domain??r,added:n.added??0,rechecking:n.rechecking??0,kept:n.kept??0})}})}_dismissTrustStatus(){this._trustStatus=null}async _command(e,r,i,{hide:n=!0,onSuccess:o}={}){let a=this.hass;if(!(!a||this._busyItems.has(e)||this._hidden.has(e))){this._busyItems=new Set([...this._busyItems,e]),this._itemErrors=kr(this._itemErrors,e),n&&(this._hidden=vr(this._hidden,[e]));try{let c=await V(a,r,i);n&&(this._hidden=$r(this._hidden,[e],this.snapshot,u=>this._listed(u))),o?.(c)}catch(c){this._hidden=yr(this._hidden,[e]);let u=h(s.actionFailed,{message:B(c)});this._listed(e)?this._itemErrors=new Map([...this._itemErrors,[e,u]]):this.showActionError(u)}finally{let c=new Set(this._busyItems);c.delete(e),this._busyItems=c}}}};F("parcels-review-card",wr);we("parcels-review-card",s.reviewCardName,s.reviewCardDescription);
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
