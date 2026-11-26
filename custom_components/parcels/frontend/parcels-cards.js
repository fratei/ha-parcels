var dt=globalThis,ct=dt.ShadowRoot&&(dt.ShadyCSS===void 0||dt.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,Qt=Symbol(),Gr=new WeakMap,Ge=class{constructor(e,r,n){if(this._$cssResult$=!0,n!==Qt)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=r}get styleSheet(){let e=this.o,r=this.t;if(ct&&e===void 0){let n=r!==void 0&&r.length===1;n&&(e=Gr.get(r)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),n&&Gr.set(r,e))}return e}toString(){return this.cssText}},Vr=t=>new Ge(typeof t=="string"?t:t+"",void 0,Qt),T=(t,...e)=>{let r=t.length===1?t[0]:e.reduce((n,i,o)=>n+(a=>{if(a._$cssResult$===!0)return a.cssText;if(typeof a=="number")return a;throw Error("Value passed to 'css' function must be a 'css' function result: "+a+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+t[o+1],t[0]);return new Ge(r,t,Qt)},Yr=(t,e)=>{if(ct)t.adoptedStyleSheets=e.map(r=>r instanceof CSSStyleSheet?r:r.styleSheet);else for(let r of e){let n=document.createElement("style"),i=dt.litNonce;i!==void 0&&n.setAttribute("nonce",i),n.textContent=r.cssText,t.appendChild(n)}},Zt=ct?t=>t:t=>t instanceof CSSStyleSheet?(e=>{let r="";for(let n of e.cssRules)r+=n.cssText;return Vr(r)})(t):t;var{is:Ns,defineProperty:Ds,getOwnPropertyDescriptor:Fs,getOwnPropertyNames:Hs,getOwnPropertySymbols:Us,getPrototypeOf:zs}=Object,ut=globalThis,Qr=ut.trustedTypes,Bs=Qr?Qr.emptyScript:"",js=ut.reactiveElementPolyfillSupport,Ve=(t,e)=>t,Jt={toAttribute(t,e){switch(e){case Boolean:t=t?Bs:null;break;case Object:case Array:t=t==null?t:JSON.stringify(t)}return t},fromAttribute(t,e){let r=t;switch(e){case Boolean:r=t!==null;break;case Number:r=t===null?null:Number(t);break;case Object:case Array:try{r=JSON.parse(t)}catch{r=null}}return r}},Jr=(t,e)=>!Ns(t,e),Zr={attribute:!0,type:String,converter:Jt,reflect:!1,useDefault:!1,hasChanged:Jr};Symbol.metadata??=Symbol("metadata"),ut.litPropertyMetadata??=new WeakMap;var se=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,r=Zr){if(r.state&&(r.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((r=Object.create(r)).wrapped=!0),this.elementProperties.set(e,r),!r.noAccessor){let n=Symbol(),i=this.getPropertyDescriptor(e,n,r);i!==void 0&&Ds(this.prototype,e,i)}}static getPropertyDescriptor(e,r,n){let{get:i,set:o}=Fs(this.prototype,e)??{get(){return this[r]},set(a){this[r]=a}};return{get:i,set(a){let d=i?.call(this);o?.call(this,a),this.requestUpdate(e,d,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??Zr}static _$Ei(){if(this.hasOwnProperty(Ve("elementProperties")))return;let e=zs(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(Ve("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(Ve("properties"))){let r=this.properties,n=[...Hs(r),...Us(r)];for(let i of n)this.createProperty(i,r[i])}let e=this[Symbol.metadata];if(e!==null){let r=litPropertyMetadata.get(e);if(r!==void 0)for(let[n,i]of r)this.elementProperties.set(n,i)}this._$Eh=new Map;for(let[r,n]of this.elementProperties){let i=this._$Eu(r,n);i!==void 0&&this._$Eh.set(i,r)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let r=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let i of n)r.unshift(Zt(i))}else e!==void 0&&r.push(Zt(e));return r}static _$Eu(e,r){let n=r.attribute;return n===!1?void 0:typeof n=="string"?n:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,r=this.constructor.elementProperties;for(let n of r.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Yr(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,r,n){this._$AK(e,n)}_$ET(e,r){let n=this.constructor.elementProperties.get(e),i=this.constructor._$Eu(e,n);if(i!==void 0&&n.reflect===!0){let o=(n.converter?.toAttribute!==void 0?n.converter:Jt).toAttribute(r,n.type);this._$Em=e,o==null?this.removeAttribute(i):this.setAttribute(i,o),this._$Em=null}}_$AK(e,r){let n=this.constructor,i=n._$Eh.get(e);if(i!==void 0&&this._$Em!==i){let o=n.getPropertyOptions(i),a=typeof o.converter=="function"?{fromAttribute:o.converter}:o.converter?.fromAttribute!==void 0?o.converter:Jt;this._$Em=i;let d=a.fromAttribute(r,o.type);this[i]=d??this._$Ej?.get(i)??d,this._$Em=null}}requestUpdate(e,r,n,i=!1,o){if(e!==void 0){let a=this.constructor;if(i===!1&&(o=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??Jr)(o,r)||n.useDefault&&n.reflect&&o===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,r,n)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,r,{useDefault:n,reflect:i,wrapped:o},a){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??r??this[e]),o!==!0||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(r=void 0),this._$AL.set(e,r)),i===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(r){Promise.reject(r)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,o]of this._$Ep)this[i]=o;this._$Ep=void 0}let n=this.constructor.elementProperties;if(n.size>0)for(let[i,o]of n){let{wrapped:a}=o,d=this[i];a!==!0||this._$AL.has(i)||d===void 0||this.C(i,void 0,o,d)}}let e=!1,r=this._$AL;try{e=this.shouldUpdate(r),e?(this.willUpdate(r),this._$EO?.forEach(n=>n.hostUpdate?.()),this.update(r)):this._$EM()}catch(n){throw e=!1,this._$EM(),n}e&&this._$AE(r)}willUpdate(e){}_$AE(e){this._$EO?.forEach(r=>r.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(r=>this._$ET(r,this[r])),this._$EM()}updated(e){}firstUpdated(e){}};se.elementStyles=[],se.shadowRootOptions={mode:"open"},se[Ve("elementProperties")]=new Map,se[Ve("finalized")]=new Map,js?.({ReactiveElement:se}),(ut.reactiveElementVersions??=[]).push("2.1.2");var er=globalThis,Xr=t=>t,pt=er.trustedTypes,en=pt?pt.createPolicy("lit-html",{createHTML:t=>t}):void 0,tr="$lit$",oe=`lit$${Math.random().toFixed(9).slice(2)}$`,rr="?"+oe,Ks=`<${rr}>`,xe=document,Qe=()=>xe.createComment(""),Ze=t=>t===null||typeof t!="object"&&typeof t!="function",nr=Array.isArray,an=t=>nr(t)||typeof t?.[Symbol.iterator]=="function",Xt=`[ 	
\f\r]`,Ye=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,tn=/-->/g,rn=/>/g,ke=RegExp(`>|${Xt}(?:([^\\s"'>=/]+)(${Xt}*=${Xt}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),nn=/'/g,sn=/"/g,ln=/^(?:script|style|textarea|title)$/i,ir=t=>(e,...r)=>({_$litType$:t,strings:e,values:r}),l=ir(1),Ka=ir(2),Wa=ir(3),S=Symbol.for("lit-noChange"),c=Symbol.for("lit-nothing"),on=new WeakMap,$e=xe.createTreeWalker(xe,129);function dn(t,e){if(!nr(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return en!==void 0?en.createHTML(e):e}var cn=(t,e)=>{let r=t.length-1,n=[],i,o=e===2?"<svg>":e===3?"<math>":"",a=Ye;for(let d=0;d<r;d++){let u=t[d],p,g,m=-1,_=0;for(;_<u.length&&(a.lastIndex=_,g=a.exec(u),g!==null);)_=a.lastIndex,a===Ye?g[1]==="!--"?a=tn:g[1]!==void 0?a=rn:g[2]!==void 0?(ln.test(g[2])&&(i=RegExp("</"+g[2],"g")),a=ke):g[3]!==void 0&&(a=ke):a===ke?g[0]===">"?(a=i??Ye,m=-1):g[1]===void 0?m=-2:(m=a.lastIndex-g[2].length,p=g[1],a=g[3]===void 0?ke:g[3]==='"'?sn:nn):a===sn||a===nn?a=ke:a===tn||a===rn?a=Ye:(a=ke,i=void 0);let f=a===ke&&t[d+1].startsWith("/>")?" ":"";o+=a===Ye?u+Ks:m>=0?(n.push(p),u.slice(0,m)+tr+u.slice(m)+oe+f):u+oe+(m===-2?d:f)}return[dn(t,o+(t[r]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),n]},Je=class t{constructor({strings:e,_$litType$:r},n){let i;this.parts=[];let o=0,a=0,d=e.length-1,u=this.parts,[p,g]=cn(e,r);if(this.el=t.createElement(p,n),$e.currentNode=this.el.content,r===2||r===3){let m=this.el.content.firstChild;m.replaceWith(...m.childNodes)}for(;(i=$e.nextNode())!==null&&u.length<d;){if(i.nodeType===1){if(i.hasAttributes())for(let m of i.getAttributeNames())if(m.endsWith(tr)){let _=g[a++],f=i.getAttribute(m).split(oe),v=/([.?@])?(.*)/.exec(_);u.push({type:1,index:o,name:v[2],strings:f,ctor:v[1]==="."?mt:v[1]==="?"?ft:v[1]==="@"?gt:Re}),i.removeAttribute(m)}else m.startsWith(oe)&&(u.push({type:6,index:o}),i.removeAttribute(m));if(ln.test(i.tagName)){let m=i.textContent.split(oe),_=m.length-1;if(_>0){i.textContent=pt?pt.emptyScript:"";for(let f=0;f<_;f++)i.append(m[f],Qe()),$e.nextNode(),u.push({type:2,index:++o});i.append(m[_],Qe())}}}else if(i.nodeType===8)if(i.data===rr)u.push({type:2,index:o});else{let m=-1;for(;(m=i.data.indexOf(oe,m+1))!==-1;)u.push({type:7,index:o}),m+=oe.length-1}o++}}static createElement(e,r){let n=xe.createElement("template");return n.innerHTML=e,n}};function Se(t,e,r=t,n){if(e===S)return e;let i=n!==void 0?r._$Co?.[n]:r._$Cl,o=Ze(e)?void 0:e._$litDirective$;return i?.constructor!==o&&(i?._$AO?.(!1),o===void 0?i=void 0:(i=new o(t),i._$AT(t,r,n)),n!==void 0?(r._$Co??=[])[n]=i:r._$Cl=i),i!==void 0&&(e=Se(t,i._$AS(t,e.values),i,n)),e}var ht=class{constructor(e,r){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=r}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:r},parts:n}=this._$AD,i=(e?.creationScope??xe).importNode(r,!0);$e.currentNode=i;let o=$e.nextNode(),a=0,d=0,u=n[0];for(;u!==void 0;){if(a===u.index){let p;u.type===2?p=new Ie(o,o.nextSibling,this,e):u.type===1?p=new u.ctor(o,u.name,u.strings,this,e):u.type===6&&(p=new _t(o,this,e)),this._$AV.push(p),u=n[++d]}a!==u?.index&&(o=$e.nextNode(),a++)}return $e.currentNode=xe,i}p(e){let r=0;for(let n of this._$AV)n!==void 0&&(n.strings!==void 0?(n._$AI(e,n,r),r+=n.strings.length-2):n._$AI(e[r])),r++}},Ie=class t{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,r,n,i){this.type=2,this._$AH=c,this._$AN=void 0,this._$AA=e,this._$AB=r,this._$AM=n,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,r=this._$AM;return r!==void 0&&e?.nodeType===11&&(e=r.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,r=this){e=Se(this,e,r),Ze(e)?e===c||e==null||e===""?(this._$AH!==c&&this._$AR(),this._$AH=c):e!==this._$AH&&e!==S&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):an(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==c&&Ze(this._$AH)?this._$AA.nextSibling.data=e:this.T(xe.createTextNode(e)),this._$AH=e}$(e){let{values:r,_$litType$:n}=e,i=typeof n=="number"?this._$AC(e):(n.el===void 0&&(n.el=Je.createElement(dn(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===i)this._$AH.p(r);else{let o=new ht(i,this),a=o.u(this.options);o.p(r),this.T(a),this._$AH=o}}_$AC(e){let r=on.get(e.strings);return r===void 0&&on.set(e.strings,r=new Je(e)),r}k(e){nr(this._$AH)||(this._$AH=[],this._$AR());let r=this._$AH,n,i=0;for(let o of e)i===r.length?r.push(n=new t(this.O(Qe()),this.O(Qe()),this,this.options)):n=r[i],n._$AI(o),i++;i<r.length&&(this._$AR(n&&n._$AB.nextSibling,i),r.length=i)}_$AR(e=this._$AA.nextSibling,r){for(this._$AP?.(!1,!0,r);e!==this._$AB;){let n=Xr(e).nextSibling;Xr(e).remove(),e=n}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},Re=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,r,n,i,o){this.type=1,this._$AH=c,this._$AN=void 0,this.element=e,this.name=r,this._$AM=i,this.options=o,n.length>2||n[0]!==""||n[1]!==""?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=c}_$AI(e,r=this,n,i){let o=this.strings,a=!1;if(o===void 0)e=Se(this,e,r,0),a=!Ze(e)||e!==this._$AH&&e!==S,a&&(this._$AH=e);else{let d=e,u,p;for(e=o[0],u=0;u<o.length-1;u++)p=Se(this,d[n+u],r,u),p===S&&(p=this._$AH[u]),a||=!Ze(p)||p!==this._$AH[u],p===c?e=c:e!==c&&(e+=(p??"")+o[u+1]),this._$AH[u]=p}a&&!i&&this.j(e)}j(e){e===c?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},mt=class extends Re{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===c?void 0:e}},ft=class extends Re{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==c)}},gt=class extends Re{constructor(e,r,n,i,o){super(e,r,n,i,o),this.type=5}_$AI(e,r=this){if((e=Se(this,e,r,0)??c)===S)return;let n=this._$AH,i=e===c&&n!==c||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,o=e!==c&&(n===c||i);i&&this.element.removeEventListener(this.name,this,n),o&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},_t=class{constructor(e,r,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=r,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){Se(this,e)}},un={M:tr,P:oe,A:rr,C:1,L:cn,R:ht,D:an,V:Se,I:Ie,H:Re,N:ft,U:gt,B:mt,F:_t},Ws=er.litHtmlPolyfillSupport;Ws?.(Je,Ie),(er.litHtmlVersions??=[]).push("3.3.3");var pn=(t,e,r)=>{let n=r?.renderBefore??e,i=n._$litPart$;if(i===void 0){let o=r?.renderBefore??null;n._$litPart$=i=new Ie(e.insertBefore(Qe(),o),o,void 0,r??{})}return i._$AI(t),i};var sr=globalThis,Z=class extends se{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let r=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=pn(r,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return S}};Z._$litElement$=!0,Z.finalized=!0,sr.litElementHydrateSupport?.({LitElement:Z});var qs=sr.litElementPolyfillSupport;qs?.({LitElement:Z});(sr.litElementVersions??=[]).push("4.2.2");var U={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},ue=t=>(...e)=>({_$litDirective$:t,values:e}),J=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,r,n){this._$Ct=e,this._$AM=r,this._$Ci=n}_$AS(e,r){return this.update(e,r)}update(e,r){return this.render(...r)}};var{I:Gs}=un,hn=t=>t;var fn=t=>t.strings===void 0,mn=()=>document.createComment(""),Oe=(t,e,r)=>{let n=t._$AA.parentNode,i=e===void 0?t._$AB:e._$AA;if(r===void 0){let o=n.insertBefore(mn(),i),a=n.insertBefore(mn(),i);r=new Gs(o,a,t,t.options)}else{let o=r._$AB.nextSibling,a=r._$AM,d=a!==t;if(d){let u;r._$AQ?.(t),r._$AM=t,r._$AP!==void 0&&(u=t._$AU)!==a._$AU&&r._$AP(u)}if(o!==i||d){let u=r._$AA;for(;u!==o;){let p=hn(u).nextSibling;hn(n).insertBefore(u,i),u=p}}}return r},pe=(t,e,r=t)=>(t._$AI(e,r),t),Vs={},bt=(t,e=Vs)=>t._$AH=e,gn=t=>t._$AH,vt=t=>{t._$AR(),t._$AA.remove()};var _n=(t,e,r)=>{let n=new Map;for(let i=e;i<=r;i++)n.set(t[i],i);return n},X=ue(class extends J{constructor(t){if(super(t),t.type!==U.CHILD)throw Error("repeat() can only be used in text expressions")}dt(t,e,r){let n;r===void 0?r=e:e!==void 0&&(n=e);let i=[],o=[],a=0;for(let d of t)i[a]=n?n(d,a):a,o[a]=r(d,a),a++;return{values:o,keys:i}}render(t,e,r){return this.dt(t,e,r).values}update(t,[e,r,n]){let i=gn(t),{values:o,keys:a}=this.dt(e,r,n);if(!Array.isArray(i))return this.ut=a,o;let d=this.ut??=[],u=[],p,g,m=0,_=i.length-1,f=0,v=o.length-1;for(;m<=_&&f<=v;)if(i[m]===null)m++;else if(i[_]===null)_--;else if(d[m]===a[f])u[f]=pe(i[m],o[f]),m++,f++;else if(d[_]===a[v])u[v]=pe(i[_],o[v]),_--,v--;else if(d[m]===a[v])u[v]=pe(i[m],o[v]),Oe(t,u[v+1],i[m]),m++,v--;else if(d[_]===a[f])u[f]=pe(i[_],o[f]),Oe(t,i[m],i[_]),_--,f++;else if(p===void 0&&(p=_n(a,f,v),g=_n(d,m,_)),p.has(d[m]))if(p.has(d[_])){let $=g.get(a[f]),ie=$!==void 0?i[$]:null;if(ie===null){let C=Oe(t,i[m]);pe(C,o[f]),u[f]=C}else u[f]=pe(ie,o[f]),Oe(t,i[m],ie),i[$]=null;f++}else vt(i[_]),_--;else vt(i[m]),m++;for(;f<=v;){let $=Oe(t,u[v+1]);pe($,o[f]),u[f++]=$}for(;m<=_;){let $=i[m++];$!==null&&vt($)}return this.ut=a,bt(t,u),S}});var bn="important",Ys=" !"+bn,j=ue(class extends J{constructor(t){if(super(t),t.type!==U.ATTRIBUTE||t.name!=="style"||t.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(t){return Object.keys(t).reduce((e,r)=>{let n=t[r];return n==null?e:e+`${r=r.includes("-")?r:r.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${n};`},"")}update(t,[e]){let{style:r}=t.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(e)),this.render(e);for(let n of this.ft)e[n]==null&&(this.ft.delete(n),n.includes("-")?r.removeProperty(n):r[n]=null);for(let n in e){let i=e[n];if(i!=null){this.ft.add(n);let o=typeof i=="string"&&i.endsWith(Ys);n.includes("-")||o?r.setProperty(n,o?i.slice(0,-11):i,o?bn:""):r[n]=i}}return S}});var N=ue(class extends J{constructor(t){if(super(t),t.type!==U.PROPERTY&&t.type!==U.ATTRIBUTE&&t.type!==U.BOOLEAN_ATTRIBUTE)throw Error("The `live` directive is not allowed on child or event bindings");if(!fn(t))throw Error("`live` bindings can only contain a single expression")}render(t){return t}update(t,[e]){if(e===S||e===c)return e;let r=t.element,n=t.name;if(t.type===U.PROPERTY){if(e===r[n])return S}else if(t.type===U.BOOLEAN_ATTRIBUTE){if(!!e===r.hasAttribute(n))return S}else if(t.type===U.ATTRIBUTE&&r.getAttribute(n)===e+"")return S;return bt(t),e}});var or="parcels";function V(t,e,r){return t.callService(or,e,r,void 0,!1)}async function vn(t,e,r){let i=(await t.callService(or,e,r,void 0,!1,!0))?.response;if(typeof i!="object"||i===null)return null;let o=i.parcel_id;return typeof o=="string"&&o!==""?o:null}function K(t,e,r={}){return t.callWS({...r,type:`${or}/${e}`})}var he={amazon:"Amazon Logistics",asendia:"Asendia",bpost:"bpost",brt:"BRT",cainiao:"Cainiao",chronopost:"Chronopost",colissimo:"Colissimo",correos:"Correos",correos_express:"Correos Express",ctt:"CTT",ctt_expresso:"CTT Expresso",deutsche_post:"Deutsche Post",dhl:"DHL",dpd:"DPD",evri:"Evri",fedex:"FedEx",gls:"GLS",hermes:"Hermes",inpost:"InPost",la_poste:"La Poste",mondial_relay:"Mondial Relay",mrw:"MRW",nacex:"Nacex",paack:"Paack",postnl:"PostNL",poste_italiane:"Poste Italiane",royal_mail:"Royal Mail",sda:"SDA",seur:"SEUR",tnt:"TNT",ups:"UPS",usps:"USPS",vinted_go:"Vinted Go",yunexpress:"YunExpress",other:"Other"};function yt(){return Object.entries(he).filter(([t])=>t!=="other").map(([t,e])=>({id:t,name:e})).sort((t,e)=>t.name.localeCompare(e.name,"en",{sensitivity:"base"})).concat([{id:"other",name:he.other??"Other"}])}function yn(t){return Object.hasOwn(he,t)?he[t]??t:t}var s={weekCardName:"Parcels week",weekCardDescription:"A Monday to Sunday calendar of your parcel deliveries.",listCardName:"Parcels without a date",listCardDescription:"Active parcels that don't have a delivery date yet.",reviewCardName:"Parcels review",reviewCardDescription:"E-mails that need a decision before Parcels uses them. Only shown to administrators.",defaultWeekTitle:"Parcels",defaultListTitle:"No date yet",defaultReviewTitle:"Parcels review",loading:"Loading parcels\u2026",loadError:"Couldn't load parcels: {message}",refreshError:"Couldn't update parcels: {message}",unknownError:"Unknown error",close:"Close",cancel:"Cancel",save:"Save",dismissMessage:"Dismiss message",configInvalid:"Invalid configuration: expected a map of options.",configTitle:'Invalid configuration: "title" must be text.',configShowArchived:'Invalid configuration: "show_archived" must be true or false.',previousWeek:"Previous week",nextWeek:"Next week",today:"Today",goToToday:"Go to the current week",weekNavigation:"Week navigation",weekOf:"Week of {range}",refresh:"Check mailboxes now",refreshFailed:"Couldn't check the mailboxes: {message}",addParcel:"Add parcel",noDeliveriesThisWeek:"No deliveries this week",noDeliveriesThisDay:"No deliveries",filterLabel:"Show parcels",filterAll:"All",filterActive:"Active",filterRecent:"Recent",filterRecentHint:"Changed or expected this week",filterCompleted:"Completed",filterEmptyWeek:"Nothing to show this week with this filter",filterNote:"Filter: {filter}",filterShowAll:"Show all",todayTag:"Today",lateGroup:"Late",lateExpected:"Late \xB7 expected {date}",lateSince:"Late \xB7 since {date}",lateExpectedLabel:"Late, expected {date}",lateSinceLabel:"Late since {date}",attentionLate:"{count} late",attentionLateLabel:"Show the late parcels",attentionReviewOne:"1 to review",attentionReview:"{count} to review",attentionReviewLabel:"Go to Needs review",reviewCardMissing:"Add the Parcels review card to this page to see what needs review.",privateParcel:"Private parcel",unnamedParcel:"Parcel",packages:"{count} packages",carrierNotKnown:"Carrier not known yet",carrierNotKnownLabel:"carrier not known yet",carrierIs:"carrier {carrier}",hasCode:"PIN in the details",pin:"PIN {code}",unknownSeller:"Unknown seller",itemsCount:"{count} items",itemsNotKnown:"Items not known yet",possibly:"Possibly: {items}",possiblyOr:" or ",itemsMore:"{name} +{count}",possibleMatches:"Possibly the same package as",possibleHintOrderMany:"Not confirmed: the carrier's e-mails for these deliveries don't name an order. Merge the one this package came in, or rule out the others.",possibleHintOrderOne:"Not confirmed: the carrier's e-mails for this delivery don't name an order. Merge it if this package came in it, or rule it out.",possibleHintDeliveryMany:"Not confirmed: the carrier's e-mails for this delivery don't name an order. Merge the order that came in it, or rule out the others.",possibleHintDeliveryOne:"Not confirmed: the carrier's e-mails for this delivery don't name an order. Merge the order if it came in it, or rule it out.",possibleHintStemMany:"Not confirmed: this parcel's e-mails name only a shipment that several packages share. Merge the package they're about, or rule out the others.",possibleHintStemOne:"Not confirmed: this parcel's e-mails name only a shipment reference. Merge the package if they're about it, or rule it out.",possibleHintShipment:"Not confirmed: an e-mail names only the shipment this package is part of. Merge it if it's about this package, or rule it out.",possibleHintAmazonMany:"Not confirmed: Amazon's tracking fits these deliveries equally well. Merge the one this package came in, or rule out the others.",possibleHintAmazonOne:"Not confirmed: Amazon's tracking fits this delivery's times. Merge it if this package came in it, or rule it out.",possibleHintAmazonDeliveryMany:"Not confirmed: Amazon's tracking of these orders fits this delivery's times. Merge the ones that came in it, and rule out the rest.",possibleHintAmazonDeliveryOne:"Not confirmed: Amazon's tracking of this order fits this delivery's times. Merge the order if it came in it, or rule it out.",candidateEmail:"1 e-mail from {name}",candidateEmails:"{count} e-mails from {name}",candidateUpdate:"1 update from {name}",candidateUpdates:"{count} updates from {name}",candidateMore:"+{count} more",carrierEmailsNoItems:"Carrier e-mails don't list items",trackingNoItems:"Tracking updates don't list items",couldAlsoBe:"Could also be: {list}",couldAlsoBeOrder:"{items} (order {tail})",notThisOne:"Not this one",notThisOneLabel:"{candidate} isn't {title}",aiBadge:"AI",aiBadgeLabel:"found by the local AI",aiFilledLabel:"details filled in by the local AI",privateLabel:"private",autoMerged:"Auto-merged \u2014 check",autoMergedLabel:"merged automatically, please check",undo:"Undo",undoMergeLabel:"Undo the automatic merge of {title}",undoFailed:"Couldn't undo the merge: {message}",keep:"Keep",keepMergeLabel:"Keep the automatic merge of {title}",keepFailed:"Couldn't keep the merge: {message}",inferred:"Delivery inferred \u2014 check",inferredLabel:"delivery inferred, please check",undoInferredLabel:"Undo the inferred delivery of {title}",undoInferredFailed:"Couldn't undo the delivery: {message}",keepInferredLabel:"Keep the inferred delivery of {title}",keepInferredFailed:"Couldn't keep the delivery: {message}",handDeliveredNotice:"Marked delivered by hand. Undo if it hasn't arrived.",undoHandDeliveredLabel:"Undo marking {title} delivered",continuesBefore:"started before this week",continuesAfter:"continues after this week",deliveredOn:"delivered {date}",returnedOn:"returned {date}",expectedOn:"expected {date}",readyForPickupSince:"ready for pickup since {date}",statusOn:"{status} on {date}",windowFrom:"from {time}",windowUntil:"until {time}",noUndatedParcels:"Every active parcel has a delivery date.",noUndatedMatch:"No parcels without a date match this filter.",tabReview:"Needs review",tabFiltered:"Filtered",tabCount:"{label} ({count})",possibleDuplicate:"Possible duplicate",suggestionTitle:"Same parcel as {parcel}?",suggestionHint:"Merge the parcel that is the same one, or keep them apart.",reasonIs:"Reason: {reason}",mergeSuggested:"Merge",mergeSuggestedLabel:"Merge {candidate} into {title}",keepApart:"Keep apart",keepApartLabel:"Keep {title} apart from these parcels",reviewTabs:"Review lists",emptyReview:"Nothing to review.",emptyFiltered:"No filtered e-mails.",filteredHint:"E-mails the local AI classed as not about a parcel, and e-mails removed from a parcel in its details. Restore reads one again.",receivedOn:"Received {date}",noSubject:"(no subject)",mailboxOf:"Mailbox: {owner}",unverifiedSender:"Unverified sender",unverifiedSenderHint:"This e-mail didn't pass the sender checks (DKIM/DMARC). Make sure it's genuine before you accept it.",aiSuggestionLabel:"read by the local AI",suggestion:"Suggestion",noSuggestion:"No suggestion. Use Edit to enter the details yourself.",accept:"Accept",acceptWithChanges:"Accept with changes",edit:"Edit",dismiss:"Dismiss",trustSender:"Trust this sender",trustSenderHint:"Treat e-mails from {domain} as a known sender from now on",trustQuestion:"Trust {domain}? This e-mail failed the sender checks, and anyone can send e-mail that claims to come from {domain}. Its e-mails waiting here will be added as they are.",trustConfirm:"Trust {domain}",trustedSenderNote:"You trust {domain}, but this e-mail failed the sender checks. Make sure it's genuine before you accept it.",trustDone:"Trusted {domain}.",trustDoneWith:"Trusted {domain}: {parts}.",trustAddedOne:"added 1 e-mail",trustAddedMany:"added {count} e-mails",trustRecheckOne:"reading 1 e-mail again",trustRecheckMany:"reading {count} e-mails again",trustKeptOne:"1 still needs review",trustKeptMany:"{count} still need review",listAnd:"{list} and {last}",unreadOne:"Couldn't read 1 e-mail",unreadMany:"Couldn't read {count} e-mails",unreadFrom:"{unread}, from {senders}.",unreadOthers:"others",unreadUnknownOne:"an unknown sender",unreadUnknownMany:"unknown senders",unreadHint:"Parcels tried each one several times over a few days. Try again reads them now; Dismiss leaves them unread.",unreadNewest:"Newest received {date}",unreadRetryHint:"Read these e-mails again now",unreadDismissHint:"Leave these e-mails unread. Parcels won't try them again.",retryDoneWith:"Tried again: {parts}.",retryNothing:"No e-mails were waiting to be read again.",retryReadOne:"read 1 e-mail",retryReadMany:"read {count} e-mails",retryFailedOne:"1 still couldn't be read",retryFailedMany:"{count} still couldn't be read",retryGoneOne:"1 is no longer in the mailbox",retryGoneMany:"{count} are no longer in the mailbox",senderChecks:"Sender check details",failedChecks:"Checks the AI answer failed",aiNotes:"Notes on the AI answer",aiNotesHint:"What Parcels changed in the answer while checking it. These aren't failed checks.",checkHeaders:"Authentication headers",checkServers:"Servers, in order",checkNoServer:"(no name)",checkOriginals:"Renamed by the mail provider",checkUsed:"Header used",checkUsedNone:"None",checkUsedHeader:"Header {n}",checkNoResult:"none",ignoreSender:"Ignore this sender",ignoreSenderHint:"Skip e-mails from {domain} from now on",restore:"Restore",clear:"Clear",clearHint:"Remove this e-mail from the list. It won't be read again.",clearAll:"Clear all",clearAllQuestion:"Clear all filtered e-mails? They won't be read again.",aiQueueOne:"1 e-mail waiting for the local AI",aiQueueMany:"{count} e-mails waiting for the local AI",aiQueueMinutes:"{queue}, about {minutes} min",aiQueueHours:"{queue}, about {hours} h",fieldKind:"Type",fieldMerchant:"Merchant",fieldCarrier:"Carrier",fieldTrackingNumber:"Tracking number",fieldTrackingNumbers:"Tracking numbers",fieldOrderNumbers:"Order numbers",fieldReference:"Shipment reference",fieldEtaStart:"Expected from",fieldEtaEnd:"Expected until",fieldWindowStart:"Time window from",fieldWindowEnd:"Time window until",fieldPickupPoint:"Pickup point",fieldPickupCode:"PIN or pickup code",fieldItems:"Items",fieldPrivate:"Private (only the owners can see it)",hintList:"Separate with commas or new lines.",hintItems:"One per line.",carrierAuto:"Detect automatically",carrierUnknown:"Unknown",details:"Parcel details",status:"Status",sinceDate:"since {date}",reportedDate:"reported {date}",dateNotKnown:"Date not known",dateNotKnownInline:"date not known",dayTimeNotKnown:"{day}, time not known",carrier:"Delivered by",notKnownYet:"Not known yet",trackOnline:"Track on the carrier's site",opensInNewTab:"(opens in a new tab)",trackingNumber:"Tracking number",copy:"Copy",copyTrackingNumber:"Copy the tracking number",copied:"Copied.",copyFailed:"Couldn't copy automatically. The number is selected, so you can copy it yourself.",merchant:"Merchant",seller:"Sold by",parcelAppName:"Name in the Parcel app",orders:"Orders",references:"Shipment reference",items:"Items",expected:"Expected",nextAttempt:"Next attempt",timeWindow:"Time window",pickupPoint:"Pickup point",collectBy:"Collect by",pickupCode:"PIN or pickup code",packagesInShipment:"Packages",showPackage:"Show package {name}",showParcel:"Show parcel {name}",parcelId:"Parcel ID",delivered:"Delivered",timeline:"Timeline",noTimeline:"No events yet.",provisional:"Provisional",provisionalHint:"Made from an order e-mail. It's completed when the shipping e-mail arrives.",archived:"Archived",private:"Private",loadingDetails:"Loading details\u2026",detailsError:"Couldn't load the details: {message}",retry:"Try again",notFound:"This parcel no longer exists.",aiNotice:"Found by the local AI. Check the details, then confirm them.",aiFilledNotice:"Some details were filled in by the local AI. Check them, then confirm.",confirm:"Confirm",confirmLabel:"Confirm the details the local AI found",confirmFilledLabel:"Confirm the details the local AI filled in",mergedNotice:"Merged automatically ({reason}). Check that it's one parcel.",mergedNoticeNoReason:"Merged automatically. Check that it's one parcel.",inferredNotice:"Probably delivered: another parcel from this shop was delivered around the expected day. Undo if it hasn't arrived.",inferredQuietNotice:"Probably delivered: no news for three weeks. Undo if it hasn't arrived.",inferredShipmentNotice:"Probably delivered: another package of this shipment was delivered. Undo if it hasn't arrived.",markDelivered:"Mark delivered",editDate:"Edit date",checkAgain:"Check again",checkingAgain:"Checking\u2026",checkAgainHint:"Read this parcel's e-mails again, and let the local AI look for what's missing",checkAgainReadOne:"Read 1 e-mail again.",checkAgainReadMany:"Read {count} e-mails again.",checkAgainGoneOne:"1 e-mail is no longer in the mailbox.",checkAgainGoneMany:"{count} e-mails are no longer in the mailbox.",checkAgainFailedOne:"1 e-mail couldn't be downloaded or read; try again later.",checkAgainFailedMany:"{count} e-mails couldn't be downloaded or read; try again later.",checkAgainNoEmails:"This parcel has no e-mails to read again.",checkAgainQueuedOne:"The local AI is checking 1 e-mail.",checkAgainQueuedMany:"The local AI is checking {count} e-mails.",checkAgainSuggest:"What it finds waits under Needs review.",checkAgainAuto:"What it finds is added to this parcel.",checkAgainNothingForAi:"There was nothing for the local AI to fill in.",checkAgainAiOff:"The local AI is off.",mergeWith:"Merge with\u2026",split:"Split\u2026",archive:"Archive",actions:"Actions",mergeIntro:"Choose the parcel to merge into this one. Likely matches come first.",mergeChoose:"Parcel",mergeConfirm:"Merge",mergeChooseFirst:"Choose a parcel first.",mergeSearch:"Search",mergeSearchPlaceholder:"Shop, item, order, number or carrier",mergeShowOlder:"Show older ({count})",mergeNoMatch:"No parcel matches the search.",noMergeCandidates:"There are no other parcels to merge with.",amazonTracking:"Amazon's tracking: delivered {when}",amazonTrackingAt:"Amazon's tracking: delivered {when} \xB7 {place}",amazonRulesOut:"Amazon's tracking rules this out: delivered at another time",amazonPointsElsewhere:"Amazon's tracking points to another package",numberTail:"No. {tail}",orderTail:"Order {tail}",splitIntro:"Choose what to move to a new parcel.",splitConfirm:"Split off",splitHint:"Choose at least one, but not all of them.",archiveQuestion:"Archive this parcel? It no longer counts as active.",dateEndBeforeStart:"The end date is before the start date.",dateEndWithoutStart:"Set a start date too.",windowEndBeforeStart:"The time window must end after it starts.",actionFailed:"That didn't work: {message}",dayAtTime:"{day} at {time}",originsTitle:"E-mails ({count})",originsAndUpdatesTitle:"E-mails and updates ({count})",originsHint:"What each e-mail and source said and added to this parcel, oldest first.",originEmail:"E-mail",originEdits:"Changed by hand",factShop:"Shop: {name}",factSeller:"Sold by {name}",factShipment:"Shipment {n}/{total}",factCarrierNumber:"{carrier} No. {tail}",factReference:"Reference {tail}",factPickup:"Pickup: {place}",factName:"Name: {name}",originItems:"Items",originAiAll:"read by the local AI",originAiPart:"partly read by the local AI",originRepeats:"{count} more from {sender}",originRepeatsLatest:"latest: {said}",moveToNewParcel:"Move to a new parcel",moveToNewParcelLabel:"Move to a new parcel: {row}",removeFromParcels:"Remove from Parcels",removeFromParcelsLabel:"Remove from Parcels: {row}",splitBlockedNothingLeft:"Can't move: nothing else would be left in this parcel.",splitBlockedShared:"Can't move: it shares the tracking number or shipment with other e-mails here.",splitBlockedOther:"Can't move this one to a new parcel.",movedNotice:"Moved to a new parcel.",movedBackNotice:"Moved back into this parcel.",removedNotice:"Removed from Parcels. It's listed under Filtered in Needs review.",removedGoneNotice:"Removed from Parcels. Nothing else was left in this parcel, so it's gone. Undo reads the e-mail again.",restoredNotice:"Restored. The e-mail was read again.",restoredElsewhereNotice:"Restored. The e-mail was read again into another parcel.",restoredReviewNotice:"Restored. The e-mail is no longer in the mailbox, so it waits under Needs review.",restoredNoParcelNotice:"Restored. The e-mail was read again, but it isn't part of a parcel now. Look under Needs review.",showOtherParcel:"Show",showOtherParcelLabel:"Show that parcel",removedFromParcel:"Removed from a parcel",addTitle:"Add parcel",addSubmit:"Add",trackingRequired:"Enter a tracking number.",returnBadge:"Return",privateReturn:"Private return",returnTo:"Return to {merchant}",returnPlain:"Return",returnPickup:"Return pickup",returnPickedUp:"Return picked up",returnReceived:"Received by the shop",returnStarted:"Return started",pickupOn:"pickup {date}",pickedUpOn:"picked up {date}",returnStartedOn:"started {date}",receivedByShopLabel:"received by the shop",pickupRuleEmail:"date from the e-mail",pickupRuleNextWorkingDay:"the e-mail says the next working day",pickupRuleAssumed:"usually the working day after the e-mail",returnDetails:"Return details",pickup:"Pickup",returnStartedDay:"Started",returnCarrier:"Carrier",returnSentBackFrom:"Original delivery",returnEmails:"E-mails",returnId:"Return ID",returnNotFound:"This return no longer exists.",returnHint:"Items you send back to a shop. Their parcel keeps its delivery; the return shows on its pickup day.",returnPickedUpAt:"Picked up",markPickedUp:"Mark picked up",undoPickedUpLabel:"Undo marking the return to {title} picked up",removeReturn:"Remove",removeReturnQuestion:"Remove this return? Its e-mails won't be read again, and a delivery worked out only from it is undone.",inferredReturnNotice:"Probably delivered: you're sending its items back. Undo if it hasn't arrived."},wn={ordered:"Ordered",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",exception:"Problem with delivery",ready_for_pickup:"Ready for pickup",returned:"Returned to sender",cancelled:"Cancelled"},kn={neighbour:"with a neighbour",mailbox:"in the mailbox",door:"at the door",reception:"at reception",garage:"in the garage",locker:"in a locker"},wt={order:"Order confirmation",shipped:"Shipped",in_transit:"In transit",out_for_delivery:"Out for delivery",delivered:"Delivered",attempted:"Delivery attempted",ready_for_pickup:"Ready for pickup",delayed:"Delayed",customs:"Held at customs",return:"Returned to sender",customer_return:"Return pickup",cancelled:"Cancelled",code:"Delivery code",not_parcel:"Not about a parcel",unknown:"Unknown"},$n={parser:"E-mail",ai:"Local AI",manual:"Added by hand",seventeentrack:"17TRACK",parcelapp:"Parcel app",inferred:"Inferred from another delivery",inferred_return:"Inferred from a return",inferred_shipment:"Inferred from another package",quiet:"No news for three weeks"},xn={unknown_sender:"Unknown sender",not_aligned:"The sender's domain isn't authenticated (DKIM/DMARC)",no_auth_header:"No authentication results in the e-mail",untrusted_authserv:"Authentication results from an unknown server",multiple_auth_results:"More than one set of authentication results, so it can't tell which is real",low_confidence:"Not sure about the details",unknown_format:"Unknown e-mail format",ai_suggestion:"Read by the local AI",ai_fill:"The local AI found details the parser missed",ai_unavailable:"The local AI wasn't available",ai_timeout:"The local AI took too long on this e-mail",ai_rejected:"The local AI's answer didn't pass the checks",restored:"Moved back from Filtered"},Sn={not_a_mapping:"The answer isn't a JSON object. Nothing in it is used.",kind_invalid:"The kind is missing, or isn't a kind Parcels knows. Nothing in the answer is used.",merchant_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',carrier_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',tracking_numbers_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',order_numbers_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',eta_start_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',eta_end_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',window_start_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',window_end_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',pickup_point_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',pickup_code_cut:'A value is as long as its cap, so the model was cut off. The value is dropped. Items are never dropped for it: a cut item ends with "\u2026".',tracking_numbers_invalid:"The field is neither a list nor a text.",order_numbers_invalid:"The field is neither a list nor a text.",items_invalid:"The field is neither a list nor a text.",tracking_numbers_too_many:"More than 20 tracking numbers, 10 order numbers or 10 items. The rest are dropped.",order_numbers_too_many:"More than 20 tracking numbers, 10 order numbers or 10 items. The rest are dropped.",items_too_many:"More than 20 tracking numbers, 10 order numbers or 10 items. The rest are dropped.",tracking_invalid:"A tracking number isn't text, isn't 4 to 40 letters and digits (spaces, dashes and dots aside), or fails its carrier's format or check digit.",tracking_not_in_email:"A tracking number isn't in the e-mail, nor a miscopy of exactly one number in it.",tracking_is_order:"A tracking number equals an order number, or the e-mail labels it as an order number.",tracking_is_pickup_code:"The e-mail writes a tracking number only as a delivery or pickup code.",tracking_is_other_number:"The e-mail labels a tracking number as a phone, tax or bank number.",order_invalid:"An order number isn't text, has more than 60 characters, or doesn't have 3 to 40 letters and digits, at least one of them a digit.",order_not_in_email:"An order number isn't in the e-mail, nor a miscopy of exactly one number in it.",order_is_part:"An order number is only part of longer, hyphen- or slash-joined numbers, and not exactly one of them can be an order number.",order_is_tracking:"An order number equals a tracking number whose format identifies it.",order_is_pickup_code:"The e-mail writes an order number only as a delivery or pickup code.",pickup_code_invalid:"The pickup code isn't text, has more than 20 characters, or isn't 3 or more letters and digits, spaces and hyphens aside.",pickup_code_not_in_email:"The pickup code isn't in the e-mail.",pickup_code_is_number:"The pickup code equals a tracking or order number.",pickup_point_invalid:"The pickup point isn't plain text, or has more than 120 characters.",merchant_invalid:"The merchant isn't plain text, or has more than 60 characters.",item_invalid:"An item isn't plain text.",carrier_unknown:"The carrier isn't text, or isn't a carrier Parcels knows.",carrier_not_in_email:"The carrier didn't send the e-mail, and the e-mail neither names it nor has a number whose format identifies it as that carrier's.",eta_start_unparsed:"A date can't be read.",eta_end_unparsed:"A date can't be read.",eta_start_out_of_range:"A date isn't between 2 days before and 60 days after the day the e-mail arrived.",eta_end_out_of_range:"A date isn't between 2 days before and 60 days after the day the e-mail arrived.",eta_end_before_start:"The last delivery day is before the first.",eta_not_delivery_date:"The date overlaps no delivery date in the e-mail, and it had passed when the e-mail arrived or the e-mail gives it as another date: a deadline, or an order, shipping, offer or replaced date.",eta_not_in_text:"The e-mail has no date, weekday or span at all. A delivery today, in an out-for-delivery e-mail, is allowed.",eta_is_mail_day:"In an order or shipping e-mail, the date is the day the e-mail arrived, and no delivery phrase in its subject or text gives that day, nor a sentence saying the customer receives the parcel that day.",window_start_unparsed:"A time can't be read.",window_end_unparsed:"A time can't be read.",window_end_before_start:"The time window doesn't end after it starts.",window_without_date:"A time window comes without a date.",not_parcel_has_tracking:"The answer says the e-mail isn't about a parcel, but gives a tracking number, or the e-mail has one whose format identifies it."},Rn={tracking_added_by_detector:"Parcels' own detector added a tracking number that the e-mail writes.",pickup_code_from_text:"The e-mail's only delivery or pickup code was used, as the answer gave none that the e-mail writes.",item_recommended:"Products the e-mail lists only under Buy again or Recommended for you were dropped.",item_is_number:"An item that was the parcel's tracking or order number, code or reference was dropped.",item_placeholder:"A generic placeholder given as an item, such as Item 1, was dropped.",kind_from_text:"The e-mail's words give a different status from the answer's, and theirs was used.",out_for_delivery_not_today:"Out for delivery, with a later delivery date and no such words in the e-mail, was read as in transit.",eta_dropped_for_kind:"A date was dropped, as no delivery is pending in e-mails of this kind.",eta_from_text:"The date by the e-mail's delivery words was used, as the answer gave another date or none.",order_moved_to_tracking:"An order number in a carrier's e-mail was the parcel's tracking number.",order_from_text:"An order number was taken as the e-mail writes it: the whole joined number, or a miscopy repaired.",tracking_from_text:"A miscopied tracking number was replaced by the e-mail's own.",merchant_is_carrier:"The shop given was this e-mail's carrier, so it was dropped.",carrier_unproven:"The shop, such as Amazon, was given as the carrier without proof that it delivers, so the carrier was left empty.",merchant_from_sender_name:"A shop given as a domain was named from the sender's name.",merchant_from_text:"A shop given as a domain was named from a line of the e-mail.",pickup_point_not_pickup:"An address the e-mail doesn't give as a pickup point was dropped.",pickup_point_generic:"A generic pickup point, such as a branch, was dropped."},Tn={same_number:"same tracking number",same_merchant_eta:"same shop and delivery date",same_merchant_day:"same shop, delivered on the expected day",same_merchant_domain:"the shop's tracked shipment followed its order",same_order:"same order",same_reference:"same shipment reference",amazon_tracking:"Amazon's tracking matches the carrier's times",parcel_switch:"the Parcel app switched Amazon's tracking to the carrier's number"};function h(t,e){return t.replace(/\{(\w+)\}/g,(r,n)=>Object.hasOwn(e,n)?String(e[n]):r)}function Y(t){if(typeof t=="string"&&t.trim())return t;if(t&&typeof t=="object"){let e=t.message;if(typeof e=="string"&&e.trim())return e;let r=t.code;if(typeof r=="string"&&r.trim())return r}return s.unknownError}var Qs=["a[href]","button:not([disabled])","input:not([disabled]):not([type='hidden'])","select:not([disabled])","textarea:not([disabled])","[tabindex]:not([tabindex='-1'])"].join(",");function Zs(t){return[...t.querySelectorAll(Qs)].filter(e=>!e.closest("[hidden], [inert]")&&e.getClientRects().length>0)}function An(t,e){if(t.key!=="Tab"||t.altKey||t.ctrlKey||t.metaKey)return;let r=Zs(e),n=r[0],i=r[r.length-1];if(!n||!i){t.preventDefault(),e.focus();return}let a=e.getRootNode().activeElement,d=a instanceof HTMLElement&&e.contains(a)&&a!==e;t.shiftKey&&(!d||a===n)?(t.preventDefault(),i.focus()):!t.shiftKey&&(!d||a===i)&&(t.preventDefault(),n.focus())}var Js="parcels-error",En="parcels-open-parcel",Pn="parcels-open-return",me=class extends Z{static properties={hass:{attribute:!1},_open:{state:!0},_busy:{state:!0},_error:{state:!0}};_returnFocus=null;_pressedBackdrop=!1;_hadFocus=!1;_session=0;constructor(){super(),this.hass=void 0,this._open=!1,this._busy=!1,this._error=null}render(){return l`<dialog
      aria-labelledby="dialog-title"
      @close=${this._onClose}
      @keydown=${this._onKeyDown}
      @pointerdown=${this._onPointerDown}
      @click=${this._onClick}
    >
      ${this._open?this.renderContent():c}
    </dialog>`}renderContent(){return c}canLightDismiss(){return!this._busy}dialogClosed(){}get isOpen(){return this._open}async showDialog(e){this._session+=1,this._returnFocus=e,this._open=!0,this._busy=!1,this._error=null,await this.updateComplete;let r=this._dialog();!r||!this._open||!this.isConnected||(r.open||r.showModal(),this.focusInDialog("[data-autofocus]"))}closeDialog(){let e=this._dialog();e?.open&&e.close(),this._finishClose(!0)}focusInDialog(e){this.renderRoot.querySelector(`dialog ${e}`)?.focus()}async focusAfterRender(e){await this.updateComplete,this._open&&this.focusInDialog(e)}async runAction(e,r){if(this._busy)return;let n=this._session;this._busy=!0,this._error=null;try{await e(),this._open&&this._session===n&&r?.()}catch(i){let o=h(s.actionFailed,{message:Y(i)});this._open&&this._session===n?this._error=o:this.dispatchEvent(new CustomEvent(Js,{detail:o}))}finally{this._session===n&&(this._busy=!1)}}disconnectedCallback(){super.disconnectedCallback(),this._finishClose(!1)}willUpdate(e){this._hadFocus=this._open&&!!this.shadowRoot?.activeElement}updated(e){this._hadFocus&&this._open&&!this.shadowRoot?.activeElement&&this.focusInDialog("[data-autofocus]"),this._hadFocus=!1}_dialog(){return this.renderRoot.querySelector("dialog")}_finishClose(e){if(!this._open)return;let r=this._returnFocus;this._returnFocus=null,this._open=!1,this._busy=!1,this._error=null,this._pressedBackdrop=!1,this.dialogClosed(),e&&r?.()}_onClose(e){let r=e.currentTarget;e.target===r&&!r.open&&this._finishClose(!0)}_onKeyDown(e){An(e,e.currentTarget)}_onPointerDown(e){this._pressedBackdrop=e.target===e.currentTarget}_onClick(e){let r=this._pressedBackdrop&&e.target===e.currentTarget;this._pressedBackdrop=!1,r&&this.canLightDismiss()&&this.closeDialog()}};var Xs=/^(\d{4})-(\d{2})-(\d{2})$/,eo=/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)(?:[.,](\d+))?(Z|[+-]\d{2}(?::?\d{2})?)?$/i,to=[31,28,31,30,31,30,31,31,30,31,30,31];function ro(t){return t%4===0&&t%100!==0||t%400===0}function no(t,e){return e===2&&ro(t)?29:to[e-1]??0}function xt(t){if(typeof t!="string")return null;let e=Xs.exec(t);if(!e)return null;let r=Number(e[1]),n=Number(e[2]),i=Number(e[3]);return n<1||n>12||i<1||i>no(r,n)?null:{year:r,month:n,day:i}}function D(t){return xt(t)!==null}function kt(t){let e=xt(t);if(!e)throw new RangeError(`Not a YYYY-MM-DD date: ${t}`);return e}function $t({year:t,month:e,day:r}){let n=e<=2?t-1:t,i=Math.floor(n/400),o=n-i*400,a=(e+9)%12,d=Math.floor((153*a+2)/5)+r-1,u=o*365+Math.floor(o/4)-Math.floor(o/100)+d;return i*146097+u-719468}function io(t){let e=t+719468,r=Math.floor(e/146097),n=e-r*146097,i=Math.floor((n-Math.floor(n/1460)+Math.floor(n/36524)-Math.floor(n/146096))/365),o=n-(365*i+Math.floor(i/4)-Math.floor(i/100)),a=Math.floor((5*o+2)/153),d=o-Math.floor((153*a+2)/5)+1,u=a<10?a+3:a-9;return{year:i+r*400+(u<=2?1:0),month:u,day:d}}function so({year:t,month:e,day:r}){return`${String(t).padStart(4,"0")}-${String(e).padStart(2,"0")}-${String(r).padStart(2,"0")}`}function ae(t,e){return so(io($t(kt(t))+e))}function ee(t,e){return $t(kt(e))-$t(kt(t))}function oo(t){return(($t(kt(t))+3)%7+7)%7}function Te(t){return ae(t,-oo(t))}function Ln(t){return Array.from({length:7},(e,r)=>ae(t,r))}function w(t,e){return t<e?-1:t>e?1:0}function In(t,e){return w(t,e)>=0?t:e}function L(t){if(typeof t!="string")return null;let e=eo.exec(t.trim());if(!e)return null;let[,r,n,i,o]=e;if(!r||!n||!D(r))return null;let a=i?`.${i.slice(0,3).padEnd(3,"0")}`:"",d="Z";if(o&&o.toUpperCase()!=="Z"){let p=o.slice(1).replace(":","").padEnd(4,"0");d=`${o[0]}${p.slice(0,2)}:${p.slice(2,4)}`}let u=Date.parse(`${r}T${n}${a}${d}`);return Number.isNaN(u)?null:u}var Cn=new Map;function ao(t){let e=Cn.get(t);if(!e){let r={calendar:"gregory",numberingSystem:"latn",year:"numeric",month:"2-digit",day:"2-digit"};try{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:t})}catch{e=new Intl.DateTimeFormat("en-US",{...r,timeZone:"UTC"})}Cn.set(t,e)}return e}function I(t,e){if(D(t))return t;let r=L(t);if(r===null)return null;let n="",i="",o="";for(let d of ao(e).formatToParts(r))d.type==="year"?n=d.value:d.type==="month"?i=d.value:d.type==="day"&&(o=d.value);let a=`${n.padStart(4,"0")}-${i}-${o}`;return D(a)?a:null}function lo(t){return[...new Set(t)]}function On(t){return lo(t.split(/[\n,;]+/).map(e=>e.trim()).filter(Boolean))}function co(t){return t.split(/\r?\n/).map(e=>e.trim()).filter(Boolean)}function te(t){let e=/^(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?$/.exec((t??"").trim());if(!e)return null;let r=Number(e[1]),n=Number(e[2]);return r>23||n>59?null:`${String(r).padStart(2,"0")}:${String(n).padStart(2,"0")}`}function Q(t){let e=t.trim();return e||null}function uo(t,e){return e&&!t?s.dateEndWithoutStart:t&&e&&w(e,t)<0?s.dateEndBeforeStart:null}function po(t,e){let r=te(t),n=te(e);return r&&n&&n<=r?s.windowEndBeforeStart:null}function Mn(t){return{eta_start:t.eta_start??"",eta_end:t.eta_end??"",window_start:te(t.window_start)??"",window_end:te(t.window_end)??""}}function St(t){let e=uo(t.eta_start,t.eta_end);if(e)return{message:e,field:e===s.dateEndWithoutStart?"eta_start":"eta_end"};let r=po(t.window_start,t.window_end);return r?{message:r,field:"window_end"}:null}function Nn(t,e){return{parcel_id:t,eta_start:Q(e.eta_start),eta_end:Q(e.eta_end),window_start:te(e.window_start),window_end:te(e.window_end)}}var Dn="shipped";function ar(t){return{kind:t?.kind||Dn,merchant:t?.merchant??"",carrier:t?.carrier??"",tracking_numbers:(t?.tracking_numbers??[]).join(", "),order_numbers:(t?.order_numbers??[]).join(", "),eta_start:t?.eta_start??"",eta_end:t?.eta_end??"",window_start:te(t?.window_start)??"",window_end:te(t?.window_end)??"",pickup_point:t?.pickup_point??"",pickup_code:t?.pickup_code??"",items:(t?.items??[]).join(`
`),reference:t?.reference??""}}function Fn(t){return{kind:t.kind.trim()||Dn,merchant:Q(t.merchant),carrier:Q(t.carrier),tracking_numbers:On(t.tracking_numbers),order_numbers:On(t.order_numbers),eta_start:Q(t.eta_start),eta_end:Q(t.eta_end),window_start:te(t.window_start),window_end:te(t.window_end),pickup_point:Q(t.pickup_point),pickup_code:Q(t.pickup_code),items:co(t.items),reference:Q(t.reference)}}function Hn(t){let e=t.tracking_number.trim();if(!e)return null;let r={tracking_number:e},n=Q(t.carrier);n&&(r.carrier=n);let i=Q(t.merchant);return i&&(r.merchant=i),t.private&&(r.private=!0),r}function lr(t,e){return t.length>0&&t.length<e}var ho="https://github.com/fratei/ha-parcels";function W(t,e){customElements.get(t)||customElements.define(t,e)}function Me(t,e,r){let n=window;Array.isArray(n.customCards)||(n.customCards=[]);let i=n.customCards;i.some(o=>o?.type===t)||i.push({type:t,name:e,description:r,preview:!0,documentationURL:ho})}var q=T`
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
`,Rt=T`
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
  .chip-late,
  .chip-title,
  .chip-meta,
  .chip-items {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  /* "Late · expected Tue 14", in a red that keeps 4.5:1 on every chip colour, light or dark. */
  .chip-late {
    font-size: 0.75rem;
    font-weight: 600;
    line-height: 1.3;
    color: var(--primary-text-color, #212121);
    color: color-mix(in srgb, var(--error-color, #db4437) 40%, var(--primary-text-color, #212121));
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
`,Ne=T`
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
`;var Un={tracking_number:"",carrier:"",merchant:"",private:!1},dr=class extends me{static properties={_form:{state:!0},_missingNumber:{state:!0}};static styles=[q,Ne,T`
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
    `];constructor(){super(),this._form=Un,this._missingNumber=!1}async open(e=null){this._form=Un,this._missingNumber=!1,await this.showDialog(e)}canLightDismiss(){return!1}renderContent(){let e=this._form,r=this._missingNumber;return l`
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
              ${yt().map(n=>l`<option value=${n.id} ?selected=${e.carrier===n.id}>
                    ${n.name}
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
    `}_onInput(e){let r=e.currentTarget,n=r.name,i=r instanceof HTMLInputElement&&r.type==="checkbox"?r.checked:r.value;this._form={...this._form,[n]:i},n==="tracking_number"&&this._missingNumber&&r.value.trim()&&(this._missingNumber=!1)}_submit(e){e.preventDefault();let r=this.hass;if(!r||this._busy)return;let n=Hn(this._form);if(!n){this._missingNumber=!0,this.focusAfterRender("#tracking-number");return}this.runAction(()=>V(r,"add",n),()=>this.closeDialog())}};W("parcels-add-dialog",dr);var Ae=ue(class extends J{constructor(t){if(super(t),t.type!==U.ATTRIBUTE||t.name!=="class"||t.strings?.length>2)throw Error("`classMap()` can only be used in the `class` attribute and must be the only part in the attribute.")}render(t){return" "+Object.keys(t).filter(e=>t[e]).join(" ")+" "}update(t,[e]){if(this.st===void 0){this.st=new Set,t.strings!==void 0&&(this.nt=new Set(t.strings.join(" ").split(/\s/).filter(n=>n!=="")));for(let n in e)e[n]&&!this.nt?.has(n)&&this.st.add(n);return this.render(e)}let r=t.element.classList;for(let n of this.st)n in e||(r.remove(n),this.st.delete(n));for(let n in e){let i=!!e[n];i===this.st.has(n)||this.nt?.has(n)||(i?(r.add(n),this.st.add(n)):(r.remove(n),this.st.delete(n)))}return S}});function mo(t){try{return Intl.DateTimeFormat.supportedLocalesOf([t]),t}catch{return"en"}}function fo(){let t=new Intl.DateTimeFormat(void 0,{hour:"numeric"}).resolvedOptions().hourCycle;return t==="h11"||t==="h12"}function De(t,e){let r=mo(t?.locale?.language||t?.language||"en"),n=t?.locale?.time_format,i;n==="12"?i=!0:n==="24"?i=!1:n==="system"&&(i=fo());let o=t?.locale?.time_zone==="local"?void 0:e||t?.config?.time_zone||void 0;return{language:r,hour12:i,timeZone:o}}var zn=new Map;function re(t,e,r){let n=e.hour!==void 0||e.timeStyle!==void 0,i={...e,timeZone:r?"UTC":t.timeZone};n&&t.hour12!==void 0&&(i.hour12=t.hour12);let o=JSON.stringify([t.language,i]),a=zn.get(o);if(!a){try{a=new Intl.DateTimeFormat(t.language,i)}catch{a=new Intl.DateTimeFormat(t.language,{...i,timeZone:void 0})}zn.set(o,a)}return a}function At(t){let e=xt(t);return e?new Date(Date.UTC(e.year,e.month-1,e.day)):null}var Et={weekday:"short",day:"numeric",month:"short"},Bn={day:"numeric",month:"short",year:"numeric"},fe={dateStyle:"medium"};function A(t,e,r=Et){let n=At(t);return n?re(e,r,!0).format(n):t}var go={weekday:"short",day:"numeric"},_o=/^en(?:-|$)/;function jn(t,e){let r=At(t);if(!r)return t;let n=re(e,go,!0);if(_o.test(n.resolvedOptions().locale)){let i=n.formatToParts(r),o=i.find(d=>d.type==="weekday")?.value,a=i.find(d=>d.type==="day")?.value;if(o&&a)return`${o} ${a}`}return n.format(r)}function F(t,e,r,n=Et){let i=At(t),o=At(e);return!i||!o?[t,e].filter(Boolean).join(" \u2013 "):t===e?re(r,n,!0).format(i):re(r,n,!0).formatRange(i,o)}function Tt(t,e){let r=/^(\d{1,2}):(\d{2})/.exec(t);if(!r)return t;let n=new Date(Date.UTC(1970,0,1,Number(r[1]),Number(r[2])));return re(e,{hour:"numeric",minute:"2-digit"},!0).format(n)}function le(t,e,r){return t&&e?`${Tt(t,r)}\u2013${Tt(e,r)}`:t?h(s.windowFrom,{time:Tt(t,r)}):e?h(s.windowUntil,{time:Tt(e,r)}):null}function E(t,e){if(!t)return"";let r=L(t);return r===null?t:re(e,{dateStyle:"medium",timeStyle:"short"},!1).format(r)}var bo={hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23"};function vo(t,e){return t%1e3!==0?!1:re({language:"en-GB",hour12:void 0,timeZone:e},bo,!1).formatToParts(t).every(n=>n.type==="literal"||n.value==="00")}function ge(t,e){let r=t?L(t):null;if(r===null)return"";let n=re(e,Et,!1).format(r);return vo(r,e.timeZone)?n:h(s.dayAtTime,{day:n,time:re(e,{timeStyle:"short"},!1).format(r)})}function z(t,e,r=Et){let n=t?L(t):null;return n===null?"":h(s.dayTimeNotKnown,{day:re(e,r,!1).format(n)})}function _e(t){if(typeof t!="string")return null;let e=t.trim();return e||null}function Kn(t){let e=t.trim();if(!/^[a-z0-9]+(?:[_-][a-z0-9]+)*$/.test(e))return e;let r=e.replace(/[_-]+/g," ");return r.charAt(0).toUpperCase()+r.slice(1)}function Xe(t,e){let r=_e(e);return r?Object.hasOwn(t,r)?t[r]??r:Kn(r):""}function R(t){let e=_e(t.carrier_name);if(e)return e;let r=_e(t.carrier);return!r||r==="other"?null:Object.hasOwn(he,r)?yn(r):Kn(r)}function O(t){return t.restricted?s.privateParcel:_e(t.merchant)??_e(t.name)??R(t)??_e(t.tracking_number)??s.unnamedParcel}function Wn(t){let e=_e(t.name);return e&&!t.restricted&&e!==O(t)?e:null}function qn(t){return t.eta_source==="parcelapp"?Ee(t.eta_source):null}function H(t){return Xe(wn,t)}function et(t){return Xe(wt,t)}function Ee(t){return Xe($n,t)}function Gn(t){switch(t.inferred_reason){case"quiet":return s.inferredQuietNotice;case"return":return s.inferredReturnNotice;case"shipment":return s.inferredShipmentNotice;default:return s.inferredNotice}}function Vn(t){return Xe(xn,t)}function cr(t,e){let r=_e(e);return r&&Object.hasOwn(t,r)?t[r]??null:null}function Yn(t){return cr(Rn,t)}function Qn(t){return cr(Sn,t)}function Zn(t){return cr(kn,t)}function Pt(t){return Xe(Tn,t)}var Ct="var(--secondary-text-color, #727272)",Jn="var(--info-color, #039be5)",yo="var(--warning-color, #ffa600)",wo="var(--success-color, #43a047)",Xn="var(--error-color, #db4437)",ko="var(--purple-color, #926bc7)",ei={ordered:Ct,shipped:Jn,in_transit:Jn,out_for_delivery:yo,delivered:wo,attempted:Xn,exception:Xn,ready_for_pickup:ko,returned:Ct,cancelled:Ct};function tt(t){return Object.hasOwn(ei,t)?ei[t]:Ct}var $o=new Set(["delivered","returned","cancelled"]);function Pe(t){return!$o.has(t)}function M(t){let e=D(t.eta_start)?t.eta_start:null,r=D(t.eta_end)?t.eta_end:null,n=e??r;return n?{start:n,end:r&&w(r,n)>=0?r:n}:null}function be(t){return Pe(t.status)}function Lt(t,e){let r=L(t.status_time),n=L(e.status_time);return r!==n?r===null?1:n===null?-1:n-r:t.id<e.id?-1:t.id>e.id?1:0}function ii(t){return t.filter(e=>be(e)&&!e.archived&&M(e)===null).sort(Lt)}var xo=7,So=9999;function ti(t){return t.replace(/[^0-9a-z]/gi,"").toUpperCase()}function ri(t){return t.merchant?.trim().toLowerCase()??""}function si(t,e){let r=t.delivered_undated&&!t.delivered_timeless;return t.status!=="delivered"||t.inferred||r?null:I(t.delivered_at,e)}function ni(t,e){let r=si(t,e);if(r)return{start:r,end:r};let n=M(t);if(n)return n;let i=I(t.delivered_at??t.status_time,e);return i?{start:i,end:i}:null}function oi(t,e,r){let n=(i,o)=>{let a=si(i,r),d=I(o.shipped_at??o.ordered_at,r);return a!==null&&d!==null&&w(a,d)<0};return n(t,e)||n(e,t)}function ur(t,e,r){let n=ni(t,r),i=ni(e,r);return!n||!i?So:w(n.end,i.start)<0?ee(n.end,i.start):w(i.end,n.start)<0?ee(i.end,n.start):0}function pr(t,{timeZone:e}){let r=new Set(t.order_numbers.map(ti).filter(Boolean)),n=ri(t),i=o=>o.order_numbers.some(a=>r.has(ti(a)))?0:n&&ri(o)===n?1:2;return(o,a)=>i(o)-i(a)||+!be(o)-+!be(a)||ur(t,o,e)-ur(t,a,e)||Lt(o,a)}function Ro(t,{today:e,timeZone:r}){if(t.archived||t.status==="cancelled")return!0;if(be(t))return!1;let n=I(t.delivered_at??t.status_time,r);return n!==null&&ee(n,e)>xo}function ai(t,e,r,n=new Set){let i=[],o=[];for(let d of t){if(d.id===e.id||d.restricted)continue;(Ro(d,r)||oi(e,d,r.timeZone)?o:i).push(d)}i.sort(pr(e,r)),o.sort(Lt);let a=(d,u)=>Number(n.has(d.id))-Number(n.has(u.id));return{likely:i.sort(a),older:o.sort(a)}}function li(t,e,r){return e.has(t)?"ruled_out":r.has(t)?"elsewhere":null}function di(t,e){let r=e.toLowerCase().split(/\s+/).filter(Boolean);return r.length?t.filter(n=>{let i=[n.merchant,R(n),n.tracking_number,...n.order_numbers,...n.items].filter(Boolean).join(" ").toLowerCase();return r.every(o=>i.includes(o))}):[...t]}function ci(t){let e=new Map;for(let r of t??[]){let n=e.get(r.parcel.id)??[];for(let i of r.candidates)n.some(o=>o.id===i.id)||n.push(i);e.set(r.parcel.id,n)}return e}function hr(t,e){let r=[],n=new Set,i=(o,a,d)=>{n.has(a.id)||(n.add(a.id),r.push({suggestionId:o.id,parcel:a,candidateId:d,reason:o.reason}))};for(let o of t??[])if(o.parcel.id===e)for(let a of o.candidates)i(o,a,a.id);else o.candidates.some(a=>a.id===e)&&i(o,o.parcel,e);return r}function ui(t,e,{timeZone:r}){let n=i=>ur(t,i.parcel,r);return e.filter(i=>!oi(t,i.parcel,r)).sort((i,o)=>n(i)-n(o)||Lt(i.parcel,o.parcel))}function pi(t,e,r){return hr(t,e).map(n=>n.parcel).filter(n=>n.id!==r&&!n.archived&&!n.restricted&&n.status!=="cancelled"&&n.status!=="returned"&&(n.items.length>0||n.order_numbers.length>0))}function hi(t){let e=t.length>1,r=t.some(n=>n.candidateId===n.parcel.id);return t.length&&t.every(n=>n.reason==="same_reference")?r?s.possibleHintShipment:e?s.possibleHintStemMany:s.possibleHintStemOne:t.length&&t.every(n=>n.reason==="amazon_tracking")?r?e?s.possibleHintAmazonDeliveryMany:s.possibleHintAmazonDeliveryOne:e?s.possibleHintAmazonMany:s.possibleHintAmazonOne:r?e?s.possibleHintDeliveryMany:s.possibleHintDeliveryOne:e?s.possibleHintOrderMany:s.possibleHintOrderOne}function fi(t,e,r){return e?.kind==="delivered"||e?.kind==="returned"||e?.kind==="late"?null:le(t.window_start,t.window_end,r)}var To={day:"numeric",month:"short"};function gi(t,e){return t?.kind!=="late"||!t.expected?null:ee(t.expected,t.from)<=6?jn(t.expected,e):A(t.expected,e,To)}function _i(t,e){let r=gi(t,e);return r&&h(t?.since?s.lateSince:s.lateExpected,{date:r})}function Ao(t,e){let r=gi(t,e);return r&&h(t?.since?s.lateSinceLabel:s.lateExpectedLabel,{date:r})}function bi(t){return!t.restricted&&R(t)===null}function vi(t){return t!==void 0&&t>1?h(s.packages,{count:String(t)}):null}function gr(t){return t.restricted?null:rt(t.merchant)??rt(t.name)}function Fe(t){return t.restricted?s.privateParcel:gr(t)??s.unknownSeller}function _r(t){if(t.restricted)return null;let e=rt(t.pickup_code);return e?h(s.pin,{code:e}):null}function yi(t,e){let r=e.placement??null,n=[],i=R(t);if(i&&n.push(i),e.showStatus){let d=H(t.status);d&&n.push(d)}let o=vi(e.count);o&&n.push(o),e.showRange&&r&&r.from!==r.to&&n.push(F(r.from,r.to,e.locale));let a=fi(t,r,e.locale);return a&&n.push(a),bi(t)&&n.push(s.carrierNotKnown),n.join(" \xB7 ")}var Eo=/^\d{1,3}\s*[x×]\s+/i,Po=/\s*(?:[,;(|[]|\s[-–—]\s)/,mi=8;function rt(t){if(typeof t!="string")return null;let e=t.replace(/\s+/g," ").trim();return e||null}function wi(t){let e=t.replace(Eo,""),r=e.search(Po);return(r>0?e.slice(0,r):e).trim()||t}function ki(t){let e=wi(t).split(" ").slice(0,3);for(;e.length>1&&e.join(" ").length>24;)e.pop();return e.join(" ")}function Co(t){let e=wi(t).split(" "),r=e[0]??t;return r.length<4&&e.length>1?`${r} ${e[1]}`:r}function ve(t){if(t.restricted)return null;let e=(t.items??[]).map(rt).filter(i=>i!==null);if(e.length===0)return null;if(e.length===1)return e[0]??null;let r=e.map(e.length===2?ki:Co),n=r.slice(0,mi);return r.length>mi&&n.push("\u2026"),`${h(s.itemsCount,{count:String(e.length)})} \xB7 ${n.join(", ")}`}function $i(t){let e=(t.items??[]).map(rt).filter(i=>i!==null),r=e[0];if(t.restricted||r===void 0)return null;let n=ki(r);return e.length>1?h(s.itemsMore,{name:n,count:String(e.length-1)}):n}function xi(t){let e=t.length===1?t[0]:void 0;if(e!==void 0){let n=ve(e);return n?h(s.possibly,{items:n}):null}let r=[...new Set(t.map($i).filter(n=>n!==null))];return r.length?h(s.possibly,{items:r.join(s.possiblyOr)}):null}function Si(t,e){let{locale:r}=e,n=e.placement??null,i=Ao(n,r),o=i?[i,Fe(t)]:[Fe(t)],a=vi(e.count);a&&o.push(a);let d=R(t);d?o.push(h(s.carrierIs,{carrier:d})):bi(t)&&o.push(s.carrierNotKnownLabel);let u=H(t.status),p=n?A(n.from,r):"";switch(n?.kind){case"delivered":o.push(h(s.deliveredOn,{date:p}));break;case"returned":o.push(h(s.returnedOn,{date:p}));break;case"pickup":o.push(h(s.readyForPickupSince,{date:p}));break;case"status":o.push(h(s.statusOn,{status:u,date:p}));break;case"late":u&&o.push(u);break;case"eta":u&&o.push(u),o.push(h(s.expectedOn,{date:F(n.from,n.to,r)}));break;default:u&&o.push(u);break}let g=fi(t,n,r);g&&o.push(g);let m=ve(t);if(m?o.push(m):e.possibly&&!t.restricted&&o.push(e.possibly),!t.restricted){t.ai?o.push(s.aiBadgeLabel):t.ai_filled&&o.push(s.aiFilledLabel),t.auto_merged&&o.push(s.autoMergedLabel),t.inferred&&o.push(s.inferredLabel);let _=_r(t);_?o.push(_):t.has_code&&o.push(s.hasCode)}return(t.private||t.restricted)&&o.push(s.privateLabel),e.continuesBefore&&o.push(s.continuesBefore),e.continuesAfter&&o.push(s.continuesAfter),o.join(", ")}function Ce(t){let e=t?.trim();if(!e)return null;if(e.length<=6)return e;let r=e.replace(/[^0-9a-z_]/gi,""),n="",i=0;for(let o=r.length-1;o>=0&&i<5;o-=1){let a=r.charAt(o);n=a+n,a!=="_"&&(i+=1)}return`\u2026${n.replace(/^_+/,"")}`}var mr=3;function Lo(t){let e=t.restricted?[]:t.senders??[];if(!e.length)return null;let r=e.slice(0,mr).map(n=>{let i=n.source!=="email",o=n.count<=1,a=i?o?s.candidateUpdate:s.candidateUpdates:o?s.candidateEmail:s.candidateEmails;return h(a,{count:String(n.count),name:n.name})});return e.length>mr&&r.push(h(s.candidateMore,{count:String(e.length-mr)})),r.join(", ")}function Io(t){let e=t.restricted?[]:t.senders??[],r=n=>n.source!=="email";return e.length&&e.every(r)?s.trackingNoItems:e.some(n=>n.carrier)&&e.every(n=>n.carrier||r(n))?s.carrierEmailsNoItems:s.itemsNotKnown}function Oo(t,e){let r=t.delivered_at??t.status_time,n=t.delivered_at?t.delivered_undated:t.status_undated,i=t.delivered_at?t.delivered_timeless:t.status_timeless;if(n)return i&&z(r,e)||s.dateNotKnownInline;if(!t.inferred){let d=ge(r,e);if(d)return d}let o=e.timeZone??Intl.DateTimeFormat().resolvedOptions().timeZone,a=I(r,o);return a?F(a,a,e):null}function nt(t,e){let r=t.amazon_tracking;if(!r)return null;let n=r.timeless?z(r.delivered,e):ge(r.delivered,e);return n?r.place?h(s.amazonTrackingAt,{when:n,place:r.place}):h(s.amazonTracking,{when:n}):null}function He(t,e){let r=[H(t.status)];if(be(t)){let a=M(t);r.push(a?F(a.start,a.end,e):null,le(t.window_start,t.window_end,e))}else r.push(Oo(t,e));let n=[R(t)??s.carrierNotKnown],i=Ce(t.tracking_number);i&&n.push(h(s.numberTail,{tail:i}));let o=Ce(t.order_numbers[0]);return o&&n.push(h(s.orderTail,{tail:o})),{title:Fe(t),when:r.filter(Boolean).join(" \xB7 "),carrier:n.join(" \xB7 "),items:ve(t),emails:Lo(t),noItems:Io(t)}}function it(t,e){let r=He(t,e);return[r.title,r.items,r.carrier,r.when].filter(Boolean).join(" \xB7 ")}var fr=3;function Ri(t){let e=t.slice(0,fr).map(r=>{let n=$i(r)??Fe(r),i=Ce(r.order_numbers[0]);return i?h(s.couldAlsoBeOrder,{items:n,tail:i}):n});return e.length?(t.length>fr&&e.push(h(s.candidateMore,{count:String(t.length-fr)})),h(s.couldAlsoBe,{list:e.join("; ")})):null}function br(t,e){let r=[],n=new Map;for(let i of t){let o=e(i),a=o===null?void 0:n.get(o);if(a){a.push(i);continue}let d=[i];r.push(d),o!==null&&n.set(o,d)}return r}function vr(t,...e){return t.restricted||t.shipment_group===null?null:JSON.stringify([t.shipment_group,t.status,...e])}function Ue(t,e){return t.id<e.id?-1:t.id>e.id?1:0}function Ti(t){return br(t,e=>vr(e)).map(e=>{let r=[...e].sort(Ue);return{parcel:e.reduce((n,i)=>Ue(i,n)<0?i:n),members:r}})}function Mo(t){return t.reduce((e,r)=>r!==null&&(e===null||r<e)?r:e,null)}function No(t){return t.reduce((e,r)=>r!==null&&(e===null||r>e)?r:e,null)}function Ai(t,e){return e.length<2?t:{...t,window_start:Mo(e.map(r=>r.window_start)),window_end:No(e.map(r=>r.window_end)),ai:e.some(r=>r.ai),ai_filled:e.some(r=>r.ai_filled),private:e.some(r=>r.private),has_code:e.some(r=>r.has_code),pickup_code:Do(e),items:Fo(t,e),auto_merged:e.find(r=>r.auto_merged)?.auto_merged??null,inferred:e.some(r=>r.inferred)}}function Do(t){let e=new Set;for(let r of t){let n=r.pickup_code?.trim();n&&e.add(n)}return e.size>0?[...e].join(", "):null}function Fo(t,e){let r=[...t.items],n=new Set(r);for(let i of e)for(let o of i.items)n.has(o)||(n.add(o),r.push(o));return r}function Ei(t,e){let r=e.shipment_group;if(r===null||e.restricted)return[];let n=t.filter(i=>i.shipment_group===r&&!i.restricted).sort((i,o)=>(i.tracking_number??"").localeCompare(o.tracking_number??"","en",{numeric:!0})||Ue(i,o));return n.length>1?n:[]}var Pi="var(--pink-color, #e91e63)",ze="mdi:package-up",Ho={email:s.pickupRuleEmail,next_working_day:s.pickupRuleNextWorkingDay,assumed:s.pickupRuleAssumed};function Ci(t){let e=t?.replace(/\s+/g," ").trim();return e||null}function ye(t,e){return t.received||t.picked_up!==null||w(t.day,e)<0}function Li(t,e){return!t.restricted&&t.pickup!==null&&!ye(t,e)}function Ii(t,e){return!t.restricted&&t.picked_up!==null&&!t.received&&w(t.day,e)>=0}function we(t){return t.restricted?s.privateReturn:Ci(t.merchant)??s.unknownSeller}function yr(t){return t?Ho[t]:null}function Oi(t){return t.restricted?null:R(t)}function st(t,e){return t.received?s.returnReceived:t.picked_up!==null?s.returnPickedUp:t.pickup===null?s.returnStarted:ye(t,e)?s.returnPickedUp:s.returnPickup}function Mi(t,e){let r=st(t,e),n=Oi(t);return n?`${r} \xB7 ${n}`:r}function Ni(t,e,r){let n=t.restricted?null:Ci(t.merchant),i=[t.restricted?s.privateReturn:n?h(s.returnTo,{merchant:n}):s.returnPlain],o=A(t.day,e),a=t.picked_up===null?"":ge(t.picked_up,e);if(a)i.push(h(s.pickedUpOn,{date:a}));else if(t.pickup===null)i.push(h(s.returnStartedOn,{date:o}));else if(ye(t,r))w(t.day,r)<=0&&i.push(h(s.pickedUpOn,{date:o}));else{i.push(h(s.pickupOn,{date:o}));let p=yr(t.pickup_rule);p&&i.push(p)}t.received&&i.push(s.receivedByShopLabel);let d=Oi(t);d&&i.push(h(s.carrierIs,{carrier:d}));let u=ve(t);return u&&i.push(u),(t.private||t.restricted)&&i.push(s.privateLabel),i.join(", ")}function Di(t,e){return t.filter(r=>r.parcel_ids.includes(e))}function kr(t){return`.chip[data-parcels~="${CSS.escape(t)}"] button.chip-main`}function Fi(t,e,r,n){let i=e?"true":"false";return l`<div class="merge-note">
    <ha-icon icon=${t.icon} aria-hidden="true"></ha-icon>
    <span class="merge-label"
      >${t.label}${t.detail?l` <span class="merge-detail">${t.detail}</span>`:c}</span
    >
    <button
      type="button"
      class="link-btn"
      aria-label=${t.undoLabel}
      aria-disabled=${i}
      @click=${r}
    >
      ${s.undo}
    </button>
    <button
      type="button"
      class="link-btn"
      aria-label=${t.keepLabel}
      aria-disabled=${i}
      @click=${n}
    >
      ${s.keep}
    </button>
  </div>`}function Uo(t,e,r){let n=r&&(t.tracking_number?.trim()??null)||null;return{title:n?`${e} ${n}`:e,detail:n}}function zo(t,e,r){let{title:n,detail:i}=e;return Fi({icon:"mdi:call-merge",label:s.autoMerged,detail:i,undoLabel:h(s.undoMergeLabel,{title:n}),keepLabel:h(s.keepMergeLabel,{title:n})},r.busy,()=>r.onUndoMerge(t),()=>r.onKeepMerge(t))}function Bo(t,e,r){let{title:n,detail:i}=e;return Fi({icon:"mdi:package-variant-closed-check",label:s.inferred,detail:i,undoLabel:h(s.undoInferredLabel,{title:n}),keepLabel:h(s.keepInferredLabel,{title:n})},r.busy,()=>r.onUndoInferred(t),()=>r.onKeepInferred(t))}var wr="\xA0";function It(t,e){let{locale:r}=e,n=e.placement??null,i=e.members&&e.members.length>1?e.members:[t],o=i.length>1,a=Ai(t,i),d=O(a),u=_r(a),p=ve(a),g=p===null&&!a.restricted?e.possibly??null:null,m=Si(a,{locale:r,placement:n,count:i.length,continuesBefore:e.continuesBefore,continuesAfter:e.continuesAfter,possibly:g}),_=yi(a,{locale:r,placement:n,count:i.length,showStatus:e.showStatus,showRange:e.showRange}),f=_i(n,r),v={chip:!0,late:f!==null,"cont-before":e.continuesBefore===!0,"cont-after":e.continuesAfter===!0,returned:a.status==="returned"},$={...e.position,"--chip-color":tt(a.status)},ie=l`<span class="chip-row" aria-hidden=${a.restricted?"true":c}>
    ${e.continuesBefore?l`<span class="cont">‹</span>`:c}
    ${a.status==="delivered"?l`<span class="check">✓</span>`:c}
    <span class="chip-text">
      ${f?l`<span class="chip-late">${f}</span>`:c}
      <span class=${Ae({"chip-title":!0,unknown:!a.restricted&&gr(a)===null})}
        >${Fe(a)}</span
      >
      <span class="chip-line">
        <span class="chip-meta">${_||wr}</span>
        ${u?l`<span class="chip-pin">${u}</span>`:c}
      </span>
      <span
        class=${Ae({"chip-items":!0,unknown:p===null&&g===null&&!a.restricted,possibly:g!==null})}
        >${p??g??(a.restricted?wr:s.itemsNotKnown)}</span
      >
    </span>
    ${(a.ai||a.ai_filled)&&!a.restricted?l`<span class="badge ai">${s.aiBadge}</span>`:c}
    ${a.has_code&&!u&&!a.restricted?l`<ha-icon class="lock" icon="mdi:dialpad" title=${s.hasCode}></ha-icon>`:c}
    ${a.private||a.restricted?l`<ha-icon class="lock" icon="mdi:lock"></ha-icon>`:c}
    ${e.continuesAfter?l`<span class="cont">›</span>`:c}
  </span>`;return a.restricted?l`<div class=${Ae(v)} style=${j($)}>
      <div class="chip-main" title=${m}>
        <span class="sr-only">${m}</span>
        ${ie}
      </div>
    </div>`:l`<div
    class=${Ae(v)}
    style=${j($)}
    data-parcel-id=${a.id}
    data-parcels=${i.map(C=>C.id).join(" ")}
  >
    <button
      type="button"
      class="chip-main"
      aria-haspopup="dialog"
      aria-label=${m}
      title=${m}
      @click=${C=>e.onOpen(t,C.currentTarget)}
    >
      ${ie}
    </button>
    ${i.map(C=>{let qe=Uo(C,d,o);return l`${C.auto_merged?zo(C,qe,e):c}${C.inferred?Bo(C,qe,e):c}`})}
  </div>`}function $r(t){return`.chip[data-return-id="${CSS.escape(t)}"] button.chip-main`}function Hi(t,e){let r=Ni(t,e.locale,e.today),n=ve(t),i={chip:!0,return:!0,done:ye(t,e.today)},o={...e.position,"--chip-color":Pi},a=l`<span class="chip-row" aria-hidden=${t.restricted?"true":c}>
    <ha-icon class="ret-icon" icon=${ze}></ha-icon>
    <span class="chip-text">
      <span class="chip-title">${we(t)}</span>
      <span class="chip-line">
        <span class="chip-meta">${Mi(t,e.today)}</span>
      </span>
      <span class="chip-items">${n??wr}</span>
    </span>
    ${t.private||t.restricted?l`<ha-icon class="lock" icon="mdi:lock"></ha-icon>`:c}
  </span>`;return t.restricted?l`<div class=${Ae(i)} style=${j(o)}>
      <div class="chip-main" title=${r}>
        <span class="sr-only">${r}</span>
        ${a}
      </div>
    </div>`:l`<div class=${Ae(i)} style=${j(o)} data-return-id=${t.id}>
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
  </div>`}function Ui(t,e){return e&&!t.restricted&&!t.archived&&be(t)&&M(t)===null}function Ot(t){return typeof t=="number"&&Number.isInteger(t)&&t>0?t:0}function xr(t){let e=t!==null&&typeof t=="object"?t:{};return{read:Ot(e.read),queued:Ot(e.queued),gone:Ot(e.gone),failed:Ot(e.failed)}}function Mt(t,e,r){return t<=0?null:t===1?e:h(r,{count:t})}function zi(t,e){if(t.read+t.gone+t.failed===0)return s.checkAgainNoEmails;let r=[Mt(t.read,s.checkAgainReadOne,s.checkAgainReadMany),Mt(t.gone,s.checkAgainGoneOne,s.checkAgainGoneMany),Mt(t.failed,s.checkAgainFailedOne,s.checkAgainFailedMany)];return t.queued>0?r.push(Mt(t.queued,s.checkAgainQueuedOne,s.checkAgainQueuedMany),e.mode==="suggest"?s.checkAgainSuggest:s.checkAgainAuto):t.read>0&&r.push(e.enabled?s.checkAgainNothingForAi:s.checkAgainAiOff),r.filter(n=>n!==null).join(" ")}var Nt={weekday:"short",day:"numeric",month:"short",year:"numeric"};function Bi(t,e){let r=H(t.status),n=t.status==="attempted"&&t.status_reported?s.reportedDate:s.sinceDate;if(t.status_undated){let i=t.status_timeless?z(t.status_time,e,fe):"";return`${r} \xB7 ${i?h(n,{date:i}):s.dateNotKnownInline}`}return t.status_time?`${r} \xB7 ${h(n,{date:E(t.status_time,e)})}`:r}function ji(t,e){let r;if(t.delivered_undated)r=t.delivered_timeless&&z(t.delivered_at,e,fe)||s.dateNotKnown;else if(t.delivered_at)r=E(t.delivered_at,e);else return null;let n=Zn(t.left_at);return n?`${r} \xB7 ${n}`:r}function Ki(t,e,r){let n=t.next_attempt;return n&&n>=e?A(n,r,Nt):null}function Wi(t,e){return t.collect_by?A(t.collect_by,e,Nt):null}var qi=["neighbour","mailbox","door","reception","garage","locker"];function x(t){return typeof t=="object"&&t!==null&&!Array.isArray(t)}function b(t){return typeof t=="string"?t:null}function k(t){return typeof t=="string"?t:""}function P(t){return Array.isArray(t)?t.filter(e=>typeof e=="string"):[]}function y(t){return typeof t=="string"&&t!==""?t:null}function ne(t){return Number.isSafeInteger(t)&&t>0?t:0}function jo(t){return typeof t=="number"&&Number.isFinite(t)&&t>=0?t:null}function B(t,e){if(!Array.isArray(t))return[];let r=[];for(let n of t){let i=e(n);i!==null&&r.push(i)}return r}function Ko(t){return t==="shop"||t==="return"||t==="shipment"||t==="quiet"?t:null}function Wo(t){return qi.includes(t)?t:null}function Gi(t){return D(t)?t:null}function ot(t){return t==="ai"||t==="manual"||t==="seventeentrack"||t==="parcelapp"?t:"parser"}function qo(t){return typeof t=="string"&&t?ot(t):null}function Go(t){return!x(t)||!y(t.origin)?null:{origin:k(t.origin),at:k(t.at),reason:k(t.reason)}}function Vo(t){if(!x(t))return null;let e=y(t.delivered);return e?{delivered:e,timeless:t.timeless===!0,place:y(t.place)}:null}function Yo(t){if(!x(t))return null;let e=y(t.name);return e?{name:e,source:t.source==="seventeentrack"||t.source==="parcelapp"?t.source:"email",carrier:t.carrier===!0,count:Math.max(1,ne(t.count))}:null}function Dt(t){if(!x(t))return null;let e=y(t.id);return e?{id:e,merchant:b(t.merchant),seller:b(t.seller),name:b(t.name),carrier:b(t.carrier),carrier_name:b(t.carrier_name),tracking_number:b(t.tracking_number),tracking_url:b(t.tracking_url),status:k(t.status),status_time:b(t.status_time),status_undated:t.status_undated===!0,status_timeless:t.status_timeless===!0,eta_start:b(t.eta_start),eta_end:b(t.eta_end),window_start:b(t.window_start),window_end:b(t.window_end),eta_source:qo(t.eta_source),delivered_at:b(t.delivered_at),delivered_undated:t.delivered_undated===!0,delivered_timeless:t.delivered_timeless===!0,status_reported:t.status_reported===!0,next_attempt:Gi(t.next_attempt),collect_by:Gi(t.collect_by),left_at:Wo(t.left_at),inferred:t.inferred===!0,inferred_reason:Ko(t.inferred_reason),delivered_by_hand:t.delivered_by_hand===!0,pickup_point:b(t.pickup_point),pickup_code:b(t.pickup_code),has_code:t.has_code===!0,order_numbers:P(t.order_numbers),references:P(t.references),items:P(t.items),private:t.private===!0,owners:P(t.owners),source:ot(t.source),ai:t.ai===!0,ai_filled:t.ai_filled===!0,auto_merged:Go(t.auto_merged),provisional:t.provisional===!0,archived:t.archived===!0,origins:P(t.origins),shipment_group:y(t.shipment_group),restricted:t.restricted===!0,senders:B(t.senders,Yo),ordered_at:y(t.ordered_at),shipped_at:y(t.shipped_at),amazon_tracking:Vo(t.amazon_tracking)}:null}function Qo(t){return x(t)?{kind:k(t.kind),merchant:b(t.merchant),carrier:b(t.carrier),tracking_numbers:P(t.tracking_numbers),order_numbers:P(t.order_numbers),eta_start:b(t.eta_start),eta_end:b(t.eta_end),window_start:b(t.window_start),window_end:b(t.window_end),pickup_point:b(t.pickup_point),pickup_code:b(t.pickup_code),items:P(t.items),reference:b(t.reference)}:null}function Zo(t){if(!x(t))return null;let e=y(t.id);return e?{id:e,created:k(t.created),received:b(t.received),sender:k(t.sender),sender_domain:k(t.sender_domain),subject:k(t.subject),mailbox_owner:b(t.mailbox_owner),reason:k(t.reason),authenticated:t.authenticated===!0,trusted_sender:t.trusted_sender===!0,checks:Xo(t.checks),fill:t.fill===!0,errors:Vi(t.errors),notes:Vi(t.notes),source:t.source==="ai"?"ai":"parser",suggestion:Qo(t.suggestion)}:null}var Jo=/^[a-z0-9_]{1,40}$/;function Vi(t){if(!Array.isArray(t))return[];let e=t.filter(r=>typeof r=="string"&&Jo.test(r));return[...new Set(e)]}function Xo(t){if(!x(t))return null;let e=ne(t.headers),r=t.used;return{headers:e,servers:Array.isArray(t.servers)?t.servers.map(n=>typeof n=="string"?n:""):[],used:Number.isSafeInteger(r)&&r>=0&&r<e?r:null,dkim:k(t.dkim),dmarc:k(t.dmarc),spf:k(t.spf),originals:ne(t.originals)}}function ea(t){if(!x(t))return null;let e=y(t.id);return e?{id:e,created:k(t.created),received:b(t.received),sender:k(t.sender),sender_domain:k(t.sender_domain),subject:k(t.subject),removed:t.removed===!0}:null}function ta(t){if(!x(t))return null;let e=y(t.id),r=Dt(t.parcel),n=B(t.candidates,Dt);return!e||!r||!n.length?null:{id:e,reason:k(t.reason),merchant:b(t.merchant),day:D(t.day)?t.day:null,parcel:r,candidates:n}}function ra(t){return t==="suggest"||t==="auto"?t:"off"}function na(t,e=Date.now()){let r=x(t)?t:{},n=y(r.time_zone)??"UTC",i=D(r.today)?r.today:I(new Date(e).toISOString(),n)??"1970-01-01";return{user_is_admin:r.user_is_admin===!0,ai_enabled:r.ai_enabled===!0,ai_mode:ra(r.ai_mode),ai_queue:ne(r.ai_queue),ai_queue_seconds:jo(r.ai_queue_seconds),dashboard_url:k(r.dashboard_url),seventeentrack:r.seventeentrack===!0,time_zone:n,today:i}}function ia(t){let e=x(t)?t:{};return{count:ne(e.count),senders:P(e.senders).filter(Boolean),unnamed:ne(e.unnamed),newest:b(e.newest)}}function Yi(t){let e=x(t)?t:{};return{read:ne(e.read),failed:ne(e.failed),gone:ne(e.gone)}}function Qi(t,e=Date.now()){let r=x(t)?t:{};return{parcels:B(r.parcels,Dt),returns:B(r.returns,aa),review:B(r.review,Zo),merge_suggestions:B(r.merge_suggestions,ta),filtered:B(r.filtered,ea),unread_emails:ia(r.unread_emails),settings:na(r.settings,e)}}function sa(t){return t==="email"||t==="next_working_day"||t==="assumed"?t:null}function oa(t){return x(t)?{time:b(t.time),label:k(t.label),source:ot(t.source)}:null}function aa(t){if(!x(t))return null;let e=y(t.id);return!e||!D(t.day)?null:{id:e,merchant:b(t.merchant),carrier:b(t.carrier),carrier_name:b(t.carrier_name),tracking_number:b(t.tracking_number),tracking_url:b(t.tracking_url),day:t.day,pickup:D(t.pickup)?t.pickup:null,pickup_rule:sa(t.pickup_rule),started:b(t.started),received:t.received===!0,picked_up:b(t.picked_up),order_numbers:P(t.order_numbers),items:P(t.items),parcel_ids:P(t.parcel_ids),emails:B(t.emails,oa),private:t.private===!0,owners:P(t.owners),archived:t.archived===!0,restricted:t.restricted===!0}}function la(t){return t==="inferred"||t==="inferred_return"||t==="inferred_shipment"||t==="quiet"?t:ot(t)}function da(t){return x(t)?{time:k(t.time),status:k(t.status),source:la(t.source),label:k(t.label),undated:t.undated===!0,timeless:t.timeless===!0}:null}function ca(t){return x(t)?{id:k(t.id),merchant:b(t.merchant),number:k(t.number),placed_at:b(t.placed_at),parcel_ids:P(t.parcel_ids)}:null}function ua(t){if(!Array.isArray(t)||t.length!==2)return null;let[e,r]=t.map(ne);return e&&r&&e<=r?[e,r]:null}function pa(t){if(!x(t))return null;let e=y(t.id);return e?{id:e,label:k(t.label),source:ot(t.source),sender_name:y(t.sender_name),name:y(t.name),time:b(t.time),status:y(t.status),kind:y(t.kind),event_time:y(t.event_time),undated:t.undated===!0,timeless:t.timeless===!0,dayless:t.dayless===!0,eta_start:D(t.eta_start)?t.eta_start:null,eta_end:D(t.eta_end)?t.eta_end:null,window_start:y(t.window_start),window_end:y(t.window_end),carrier:y(t.carrier),carrier_name:y(t.carrier_name),tracking_number:y(t.tracking_number),reference:y(t.reference),merchant:y(t.merchant),seller:y(t.seller),order_numbers:P(t.order_numbers),items:P(t.items),pickup_point:y(t.pickup_point),shipment:ua(t.shipment),email:t.email===!0,edits:t.edits===!0,part_of:y(t.part_of),split_blocked:y(t.split_blocked)}:null}function Zi(t){if(!x(t))return null;let e=Dt(t.parcel);return e?{parcel:e,timeline:B(t.timeline,da),orders:B(t.orders,ca),origins:B(t.origins,pa),contradicted:B(t.contradicted,y),elsewhere:B(t.elsewhere,y)}:null}var ha=6e4;function Le(t){let e=t?.trim();return e||null}function ma(t,e){let r=[t,...e],n=r.find(u=>u.status||u.kind)??t,i=r.find(u=>u.eta_start||u.window_start||u.window_end)??t,o=r.find(u=>u.carrier||u.carrier_name)??t,a=u=>r.find(p=>p[u]!==null&&p[u]!=="")?.[u]??t[u],d=u=>[...new Set(r.flatMap(p=>p[u]))];return{...t,status:n.status,kind:n.kind,event_time:n.event_time,undated:n.undated,timeless:n.timeless,dayless:n.dayless,eta_start:i.eta_start,eta_end:i.eta_end,window_start:i.window_start,window_end:i.window_end,carrier:o.carrier,carrier_name:o.carrier_name,tracking_number:a("tracking_number"),reference:a("reference"),merchant:a("merchant"),seller:a("seller"),pickup_point:a("pickup_point"),shipment:a("shipment"),name:a("name"),order_numbers:d("order_numbers"),items:d("items")}}function fa(t){return t.edits?s.originEdits:t.email?Le(t.sender_name)??Le(t.label)??s.originEmail:Le(t.label)??Ee(t.source)}function ga(t,e){let r=[],i=(t.kind&&t.kind!=="unknown"&&t.kind!=="not_parcel"?et(t.kind):"")||(t.status?H(t.status):"");if(i){r.push(i);let a=t.event_time?L(t.event_time):null,d=t.time?L(t.time):null;t.undated?r.push(t.timeless&&z(t.event_time,e)||s.dateNotKnownInline):a!==null&&(d===null||Math.abs(a-d)>=ha)&&r.push(ge(t.event_time,e))}if(t.eta_start){let a=F(t.eta_start,t.eta_end??t.eta_start,e);r.push(h(s.expectedOn,{date:a}))}let o=le(t.window_start,t.window_end,e);return o&&r.push(o),r.join(" \xB7 ")}function _a(t){let e=[],r=Le(t.merchant);r&&e.push(h(s.factShop,{name:r}));let n=Le(t.seller);n&&e.push(h(s.factSeller,{name:n}));for(let p of t.order_numbers){let g=Ce(p);g&&e.push(h(s.orderTail,{tail:g}))}if(t.shipment){let[p,g]=t.shipment;e.push(h(s.factShipment,{n:String(p),total:String(g)}))}let i=R(t),o=Ce(t.tracking_number);i&&o?e.push(h(s.factCarrierNumber,{carrier:i,tail:o})):i?e.push(i):o&&e.push(h(s.numberTail,{tail:o}));let a=Ce(t.reference);a&&e.push(h(s.factReference,{tail:a}));let d=Le(t.pickup_point);d&&e.push(h(s.factPickup,{place:d}));let u=Le(t.name);return u&&e.push(h(s.factName,{name:u})),e}function Ji(t,e){let r=new Set(t.map(o=>o.id)),n=new Map;for(let o of t)o.part_of&&o.part_of!==o.id&&r.has(o.part_of)&&n.set(o.part_of,[...n.get(o.part_of)??[],o]);let i=[];for(let o of t){if(o.part_of&&o.part_of!==o.id&&r.has(o.part_of))continue;let a=n.get(o.id)??[],d=ma(o,a),u=fa(d),p=null;o.source==="ai"?p="all":a.length&&(p="part"),i.push({ids:[o.id,...a.map(g=>g.id)],lead:o.id,header:u,when:ge(o.time,e),said:ga(d,e),facts:_a(d),items:d.items.filter(g=>g.trim()),ai:p,email:o.email,edits:o.edits,splitBlocked:o.split_blocked,sender:`${o.email?"email":o.source}:${u}`})}return i}function Xi(t){let e=new Map,r=new Map;for(let o of t){if(!o.email||o.edits)continue;let a=e.get(o.sender),d=[...o.facts,...o.items.map(u=>`\0${u}`)];a&&d.every(u=>a.has(u))&&r.set(o.sender,[...r.get(o.sender)??[],o]),e.set(o.sender,new Set([...a??[],...d]))}let n=new Map;for(let o of r.values())if(o.length>=2)for(let a of o)n.set(a.lead,o);let i=[];for(let o of t){let a=n.get(o.lead);if(!a){i.push({type:"row",row:o});continue}let d=a[a.length-1];d.lead===o.lead&&i.push({type:"repeats",key:d.lead,header:o.header,rows:a,latest:d})}return i}function es(t){let e=t.every(r=>r.email)?s.originsTitle:s.originsAndUpdatesTitle;return h(e,{count:String(t.length)})}function ts(t,e){let r=new Set(e);return t.filter(n=>r.has(n.lead)).flatMap(n=>n.ids)}function rs(t){switch(t){case null:return null;case"nothing_left":return s.splitBlockedNothingLeft;case"shared_number":case"shared_shipment":return s.splitBlockedShared;default:return s.splitBlockedOther}}function ns(t,e,r){let n=t.parcels[0];return t.review!==null?{notice:"review",follow:null,show:null}:t.parcels.includes(e)?{notice:"restored",follow:null,show:null}:n===void 0?{notice:"noParcel",follow:null,show:null}:r?{notice:"restored",follow:n,show:null}:{notice:"elsewhere",follow:null,show:n}}function Ft(t){if(typeof t!="string")return null;let e=t.trim();if(!e)return null;let r;try{r=new URL(e)}catch{return null}return r.protocol!=="https:"||!r.hostname||r.username||r.password?null:r.href}var is={parcel:/^p_[0-9a-f]{1,64}$/,return:/^ret_[0-9a-f]{1,64}$/};function ss(t){return Object.hasOwn(is,t)}function os(t){try{return decodeURIComponent(t.replaceAll("+"," "))}catch{return t}}function as(t){return t.replace(/^\?/,"").split("&").filter(e=>e!=="")}function ls(t){let e=t.indexOf("=");return os(e<0?t:t.slice(0,e))}function ds(t){for(let e of as(t)){let r=ls(e);if(!ss(r))continue;let n=e.indexOf("="),i=n<0?"":os(e.slice(n+1));if(is[r].test(i))return{kind:r,id:i}}return null}function cs(t){let e=as(t),r=e.filter(n=>!ss(ls(n)));return r.length===e.length?t:r.length?`?${r.join("&")}`:""}var ba={restored:s.restoredNotice,elsewhere:s.restoredElsewhereNotice,review:s.restoredReviewNotice,noParcel:s.restoredNoParcelNotice},us={eta_start:"",eta_end:"",window_start:"",window_end:""},va=6;function ya(t){return t.map((e,r)=>({entry:e,index:r,time:L(e.time)??-1/0})).sort((e,r)=>r.time-e.time||r.index-e.index).map(({entry:e})=>e)}var Sr=class extends me{static properties={snapshot:{attribute:!1},locale:{attribute:!1},_parcelId:{state:!0},_details:{state:!0},_loading:{state:!0},_loadError:{state:!0},_mode:{state:!0},_copyState:{state:!0},_dateForm:{state:!0},_formError:{state:!0},_mergeTarget:{state:!0},_mergeQuery:{state:!0},_mergeOlder:{state:!0},_mergeHint:{state:!0},_splitSelection:{state:!0},_pendingPrivate:{state:!0},_checking:{state:!0},_checkStatus:{state:!0},_originsOpen:{state:!0},_openFolds:{state:!0},_originNotice:{state:!0}};static styles=[q,Ne,T`
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
      .merge-line.ruled-out {
        display: flex;
        align-items: flex-start;
        gap: 4px;
        color: var(--error-color, #db4437);
        --mdc-icon-size: 16px;
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
    `];_request=0;_checkRun=0;_loadedKey="";_rowsCache=null;constructor(){super(),this.snapshot=null,this.locale=De(void 0),this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._copyState="idle",this._dateForm=us,this._formError=null,this._mergeTarget="",this._mergeQuery="",this._mergeOlder=!1,this._mergeHint=!1,this._splitSelection=[],this._pendingPrivate=null,this._checking=!1,this._checkStatus=null,this._originsOpen=!1,this._openFolds=new Set,this._originNotice=null}async open(e,r=null){this._parcelId=e,this._details=null,this._loadError=null,this._mode="view",this._copyState="idle",this._formError=null,this._pendingPrivate=null,this._checkRun+=1,this._checking=!1,this._checkStatus=null,this._resetOrigins(),this._load(),await this.showDialog(r)}_switchTo(e){this._busy||e===this._parcelId||(this._parcelId=e,this._details=null,this._loadError=null,this._error=null,this._mode="view",this._copyState="idle",this._formError=null,this._pendingPrivate=null,this._checkStatus=null,this._resetOrigins(),this._load(),this.focusAfterRender("[data-current-package]"))}_resetOrigins(){this._originsOpen=!1,this._openFolds=new Set,this._originNotice=null}dialogClosed(){this._request+=1,this._parcelId=null,this._details=null,this._loading=!1,this._loadError=null,this._mode="view",this._pendingPrivate=null,this._checkRun+=1,this._checking=!1,this._checkStatus=null,this._resetOrigins()}canLightDismiss(){return this._mode==="view"&&!this._busy}willUpdate(e){if(super.willUpdate(e),!e.has("snapshot")||!this.isOpen||!this.snapshot)return;this._pendingPrivate=null;let r=this.snapshot.parcels.find(n=>n.id===this._parcelId);r&&JSON.stringify(r)!==this._loadedKey&&this._load()}get _parcel(){let e=this._parcelId;return e===null?null:this.snapshot?this.snapshot.parcels.find(r=>r.id===e)??null:this._details?.parcel??null}async _load(){let e=this.hass,r=this._parcelId;if(!e||r===null)return;let n=++this._request,i=this.snapshot?.parcels.find(o=>o.id===r);this._loadedKey=i?JSON.stringify(i):"",this._loading=!0,this._loadError=null;try{let o=await K(e,"get",{parcel_id:r});if(n!==this._request)return;let a=Zi(o);if(!a)throw new Error(s.unknownError);this._details=a}catch(o){n===this._request&&(this._loadError=Y(o))}finally{n===this._request&&(this._loading=!1)}}renderContent(){let e=this._parcel;return l`
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
      <span class="badge" style=${j({"--badge-color":tt(e.status)})}>
        ${H(e.status)}
      </span>
      ${(e.ai||e.ai_filled)&&!e.restricted?l`<span class="badge ai" title=${r}>
            ${s.aiBadge}<span class="sr-only">, ${r}</span>
          </span>`:c}
      ${e.private||e.restricted?l`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${s.private}
          </span>`:c}
      ${e.provisional?l`<span class="badge info">${s.provisional}</span>`:c}
      ${this._returnsOf(e).length?l`<span class="badge return">
            <ha-icon icon=${ze} aria-hidden="true"></ha-icon>${s.returnBadge}
          </span>`:c}
      ${e.archived?l`<span class="badge">${s.archived}</span>`:c}
    </div>`}_returnsOf(e){return e.restricted?[]:Di(this.snapshot?.returns??[],e.id)}_renderBody(e){if(!e)return this.snapshot||!this._loading&&!this._loadError?l`<p class="empty">${s.notFound}</p>`:this._renderLoadState();switch(this._mode){case"date":return this._renderDateForm();case"merge":return this._renderMerge(e);case"split":return this._renderSplit();case"archive":return l`<p>${s.archiveQuestion}</p>`;default:return this._renderView(e)}}_renderLoadState(){return this._loadError?l`<div class="alert error" role="alert">
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
          </div>`:c}
      ${!r&&e.auto_merged?this._renderMergeNotice(e):c}
      ${!r&&e.inferred?this._renderInferredNotice(e):c}
      ${!r&&e.delivered_by_hand?this._renderHandNotice(e):c}
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
    `}get _rows(){let e=this._details;if(!e)return[];let r=this._rowsCache;if(r?.details===e&&r.locale===this.locale)return r.rows;let n=Ji(e.origins,this.locale);return this._rowsCache={details:e,locale:this.locale,rows:n},n}get _splitRows(){return this._rows.filter(e=>!e.edits)}get _splitChosen(){let e=new Set(this._splitRows.map(r=>r.lead));return this._splitSelection.filter(r=>e.has(r))}_renderOrigins(){let e=this._rows;if(!e.length)return c;let r=this._splitRows.length>=2;return l`<details class="origins" .open=${this._originsOpen} @toggle=${this._onOriginsToggle}>
      <summary class="section-title" data-origins-summary>${es(e)}</summary>
      <p class="hint">${s.originsHint}</p>
      <ol class="origin-list">
        ${Xi(e).map(n=>this._renderOriginEntry(n,r))}
      </ol>
    </details>`}_renderOriginEntry(e,r){if(e.type==="row")return l`<li class="origin" data-origin=${e.row.lead}>
        ${this._renderOriginBody(e.row,!1)}${this._renderRowActions(e.row,r)}
      </li>`;let n=this._openFolds.has(e.key),i=e.latest.said;return l`<li class="origin fold">
      <span class="origin-line">
        <button
          type="button"
          class="link-btn fold-toggle"
          aria-expanded=${n?"true":"false"}
          @click=${()=>this._toggleFold(e.key)}
        >
          <ha-icon icon=${n?"mdi:chevron-up":"mdi:chevron-down"} aria-hidden="true"></ha-icon>
          ${h(s.originRepeats,{count:String(e.rows.length),sender:e.header})}
        </button>
        ${i?l`<span class="muted">· ${h(s.originRepeatsLatest,{said:i})}</span>`:c}
      </span>
      ${n?l`<ol class="origin-list">
            ${e.rows.map(o=>l`<li class="origin" data-origin=${o.lead}>
                ${this._renderOriginBody(o,!1)}${this._renderRowActions(o,r)}
              </li>`)}
          </ol>`:c}
    </li>`}_renderOriginBody(e,r){let n=c;e.items.length&&r?n=l`<span class="origin-line origin-items">
        ${e.items.map(o=>l`<span class="origin-item">${o}</span>`)}
      </span>`:e.items.length&&(n=l`<ul class="origin-items" aria-label=${s.originItems}>
        ${e.items.map(o=>l`<li>${o}</li>`)}
      </ul>`);let i=e.ai==="all"?s.originAiAll:s.originAiPart;return l`<span class="origin-line">
        <strong>${e.header}</strong>${e.when?l`<span class="muted"> · ${e.when}</span>`:c}${e.ai?l`<span class="muted"> · ${i}</span>`:c}
      </span>
      ${e.said?l`<span class="origin-line">${e.said}</span>`:c}
      ${e.facts.length?l`<span class="origin-line muted">${e.facts.join(" \xB7 ")}</span>`:c}
      ${n}`}_renderRowActions(e,r){let n=e.email&&this.snapshot?.settings.user_is_admin===!0;if(e.edits||!r&&!n)return c;let i=r?rs(e.splitBlocked):null,o=this._busy?"true":"false",a=e.when?`${e.header} \xB7 ${e.when}`:e.header,d=c;return i?d=l`<span class="hint">${i}</span>`:r&&(d=l`<button
        type="button"
        class="btn"
        data-move
        aria-label=${h(s.moveToNewParcelLabel,{row:a})}
        aria-disabled=${o}
        @click=${()=>this._moveRow(e)}
      >
        ${s.moveToNewParcel}
      </button>`),l`<span class="row-actions">
      ${d}
      ${n?l`<button
            type="button"
            class="btn"
            data-remove
            aria-label=${h(s.removeFromParcelsLabel,{row:a})}
            aria-disabled=${o}
            @click=${()=>this._removeRow(e)}
          >
            ${s.removeFromParcels}
          </button>`:c}
    </span>`}_renderPossible(e){let r=this.snapshot?.merge_suggestions,n=ui(e,hr(r,e.id),this._dayContext());if(!n.length)return c;let i=this.locale,o=this._busy?"true":"false",a=O(e);return l`<section class="possible" aria-labelledby="possible-title">
      <h3 class="section-title" id="possible-title">${s.possibleMatches}</h3>
      <p class="hint">${hi(n)}</p>
      <ul class="possible-list">
        ${n.map(d=>{let u=it(d.parcel,i);return l`<li class="possible-item" data-possible=${d.parcel.id}>
            ${this._renderCandidateLines(d.parcel,e.id)}
            <span class="possible-actions">
              <button
                type="button"
                class="btn"
                data-accept
                aria-label=${h(s.mergeSuggestedLabel,{candidate:u,title:a})}
                aria-disabled=${o}
                @click=${()=>this._acceptPossible(d)}
              >
                ${s.mergeSuggested}
              </button>
              <button
                type="button"
                class="btn"
                data-dismiss
                aria-label=${h(s.notThisOneLabel,{candidate:u,title:a})}
                aria-disabled=${o}
                @click=${()=>this._dismissPossible(d)}
              >
                ${s.notThisOne}
              </button>
            </span>
          </li>`})}
      </ul>
    </section>`}_renderMergeNotice(e){let r=Pt(e.auto_merged?.reason),n=this._busy?"true":"false",i=O(e);return l`<div class="alert warning">
      <ha-icon icon="mdi:call-merge" aria-hidden="true"></ha-icon>
      <span class="grow">
        ${r?h(s.mergedNotice,{reason:r}):s.mergedNoticeNoReason}
      </span>
      <button
        type="button"
        class="btn"
        aria-label=${h(s.undoMergeLabel,{title:i})}
        aria-disabled=${n}
        @click=${this._undoMerge}
      >
        ${s.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${h(s.keepMergeLabel,{title:i})}
        aria-disabled=${n}
        @click=${this._keepMerge}
      >
        ${s.keep}
      </button>
    </div>`}_renderInferredNotice(e){let r=this._busy?"true":"false",n=O(e);return l`<div class="alert warning">
      <ha-icon icon="mdi:package-variant-closed-check" aria-hidden="true"></ha-icon>
      <span class="grow">${Gn(e)}</span>
      <button
        type="button"
        class="btn"
        aria-label=${h(s.undoInferredLabel,{title:n})}
        aria-disabled=${r}
        @click=${this._undoDelivery}
      >
        ${s.undo}
      </button>
      <button
        type="button"
        class="btn"
        aria-label=${h(s.keepInferredLabel,{title:n})}
        aria-disabled=${r}
        @click=${this._keepInferred}
      >
        ${s.keep}
      </button>
    </div>`}_renderHandNotice(e){return l`<div class="alert">
      <ha-icon icon="mdi:package-variant-closed-check" aria-hidden="true"></ha-icon>
      <span class="grow">${s.handDeliveredNotice}</span>
      <button
        type="button"
        class="btn"
        data-undo-delivered
        aria-label=${h(s.undoHandDeliveredLabel,{title:O(e)})}
        aria-disabled=${this._busy?"true":"false"}
        @click=${this._undoDelivery}
      >
        ${s.undo}
      </button>
    </div>`}_renderFacts(e){let r=this.locale,n=M(e),i=le(e.window_start,e.window_end,r),o=R(e),a=e.restricted?null:Ft(e.tracking_url),d=e.tracking_number?.trim()??"",u=this._details?.orders??[],p=Ei(this.snapshot?.parcels??[],e),g=this._details?.parcel.id===e.id?this._details.parcel:null,m=e.has_code?g?.pickup_code??null:null,_=this._returnsOf(e),f=(G,Ms)=>l`<div><dt>${G}</dt><dd>${Ms}</dd></div>`,v=ji(e,r),$=Ki(e,this.snapshot?.settings.today??"",r),ie=Wi(e,r),C=qn(e),qe=Wn(e);return l`<dl class="facts">
      ${f(s.status,Bi(e,r))}
      ${v?f(s.delivered,v):c}
      ${$?f(s.nextAttempt,$):c}
      ${n?f(s.expected,`${F(n.start,n.end,r,Nt)}${C?` \xB7 ${C}`:""}`):c}
      ${i?f(s.timeWindow,i):c}
      ${_.length?f(s.returnBadge,l`<ul>
              ${_.map(G=>this._renderReturnLink(G))}
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
      ${p.length?f(s.packagesInShipment,l`<ul class="packages">
              ${p.map(G=>this._renderPackage(G,e.id))}
            </ul>`):c}
      ${e.merchant?f(s.merchant,e.merchant):c}
      ${e.seller?f(s.seller,e.seller):c}
      ${qe?f(s.parcelAppName,qe):c}
      ${u.length?f(s.orders,l`<ul>
              ${u.map(G=>l`<li>
                    ${G.number}${G.placed_at?` \xB7 ${E(G.placed_at,r)}`:""}
                  </li>`)}
            </ul>`):e.order_numbers.length?f(s.orders,e.order_numbers.join(", ")):c}
      ${e.references.length?f(s.references,e.references.join(", ")):c}
      ${e.items.length?f(s.items,l`<ul>
              ${e.items.map(G=>l`<li>${G}</li>`)}
            </ul>`):c}
      ${e.pickup_point?f(s.pickupPoint,e.pickup_point):c}
      ${ie?f(s.collectBy,ie):c}
      ${m?f(s.pickupCode,m):c}
      ${e.restricted?c:f(s.parcelId,e.id)}
    </dl>`}_renderReturnLink(e){let r=this.snapshot?.settings.today??"",n=`${st(e,r)} \xB7 ${A(e.day,this.locale)}`;return e.restricted?l`<li>${n}</li>`:l`<li>
      <button
        type="button"
        class="link-btn"
        aria-haspopup="dialog"
        aria-disabled=${this._busy?"true":"false"}
        @click=${()=>this._openReturn(e.id)}
      >
        ${n}
      </button>
    </li>`}_openReturn(e){this._busy||(this.closeDialog(),this.dispatchEvent(new CustomEvent(Pn,{detail:e})))}_renderPackage(e,r){let n=this.locale,i=e.tracking_number?.trim()||O(e),o=M(e),a=e.delivered_undated?e.delivered_timeless&&z(e.delivered_at,n,fe)||s.dateNotKnownInline:e.delivered_at?E(e.delivered_at,n):o?F(o.start,o.end,n):"",d=[H(e.status),a].filter(Boolean).join(" \xB7 ");return e.id===r?l`<li aria-current="true" tabindex="-1" data-current-package>
        <strong>${i}</strong>${d?` \xB7 ${d}`:""}
      </li>`:l`<li>
      <button
        type="button"
        class="link-btn"
        aria-label=${h(s.showPackage,{name:i})}
        aria-disabled=${this._busy?"true":"false"}
        @click=${()=>this._switchTo(e.id)}
      >
        ${i}</button
      >${d?` \xB7 ${d}`:""}
    </li>`}_renderTimeline(e){if(!e.length)return l`<p class="muted">${s.noTimeline}</p>`;let r=this.locale;return l`<ol class="timeline">
      ${ya(e).map(n=>{let i=H(n.status),o=n.label.trim(),d=[n.undated?n.timeless&&z(n.time,r,fe)||s.dateNotKnown:E(n.time,r),Ee(n.source)].filter(Boolean).join(" \xB7 ");return l`<li style=${j({"--dot-color":tt(n.status)})}>
          <span class="dot" aria-hidden="true"></span>
          <div class="entry-title">${i}</div>
          ${o&&o!==i?l`<div>${o}</div>`:c}
          ${d?l`<div class="entry-meta">${d}</div>`:c}
        </li>`})}
    </ol>`}_renderDateForm(){let e=this._dateForm,r=this._formError,n=(i,o,a,d=!1)=>{let u=r?.field===i;return l`<label class="field">
        <span class="field-label">${o}</span>
        <input
          type=${a}
          name=${i}
          .value=${N(e[i])}
          ?data-first=${d}
          aria-invalid=${u?"true":"false"}
          aria-describedby=${u?"date-error":c}
          @input=${this._onDateInput}
        />
      </label>`};return l`<form id="date-form" novalidate @submit=${this._saveDate}>
      <div class="form-grid">
        ${n("eta_start",s.fieldEtaStart,"date",!0)}
        ${n("eta_end",s.fieldEtaEnd,"date")}
        ${n("window_start",s.fieldWindowStart,"time")}
        ${n("window_end",s.fieldWindowEnd,"time")}
      </div>
      ${r?l`<div class="alert error" id="date-error" role="alert">
            <span class="grow">${r.message}</span>
          </div>`:c}
    </form>`}_renderMerge(e){let{pool:r,shown:n,target:i}=this._mergeChoice(e),o=r.likely.length+r.older.length;if(!o)return l`<p class="empty">${s.noMergeCandidates}</p>`;let a=this._mergeQuery.trim()!=="",d=o>va,u=this._mergeOlder&&!a?r.likely.length:-1,p=!a&&!this._mergeOlder&&r.older.length>0,g=nt(e,this.locale);return l`<p id="merge-intro">${s.mergeIntro}</p>
      ${g?l`<p class="hint" id="merge-evidence" data-amazon-tracking>${g}</p>`:c}
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
      <fieldset class="merge-list" aria-describedby=${g?"merge-intro merge-evidence":"merge-intro"}>
        <legend class="sr-only">${s.mergeChoose}</legend>
        ${n.map((m,_)=>this._renderCandidate(m,e.id,{checked:m.id===i,first:!d&&_===0,olderFirst:_===u}))}
        ${a&&!n.length?l`<p class="empty">${s.mergeNoMatch}</p>`:c}
      </fieldset>
      ${p?l`<button
            type="button"
            class="link-btn"
            ?data-first=${!d&&!n.length}
            @click=${this._showOlderMerge}
          >
            ${h(s.mergeShowOlder,{count:String(r.older.length)})}
          </button>`:c}
      ${this._mergeHint&&!i?l`<p class="hint merge-hint" role="alert">${s.mergeChooseFirst}</p>`:c}`}_renderCandidate(e,r,n){return l`<label class="merge-option">
      <input
        type="radio"
        name="merge-target"
        value=${e.id}
        .checked=${N(n.checked)}
        ?data-first=${n.first}
        ?data-older-first=${n.olderFirst}
        @change=${this._onMergeTarget}
      />
      ${this._renderCandidateLines(e,r)}
    </label>`}_renderCandidateLines(e,r){let n=He(e,this.locale),i=n.items?null:Ri(pi(this.snapshot?.merge_suggestions,e.id,r)),o=nt(e,this.locale),a=li(e.id,this._ruledOut(r),this._pointsElsewhere(r));return l`<span class="merge-lines">
      <span class="merge-line"><strong>${n.title}</strong> · ${n.when}</span>
      ${a==="ruled_out"?l`<span class="merge-line ruled-out" data-ruled-out>
            <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
            <span>${s.amazonRulesOut}</span>
          </span>`:c}
      ${a==="elsewhere"?l`<span class="merge-line ruled-out" data-points-elsewhere>
            <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
            <span>${s.amazonPointsElsewhere}</span>
          </span>`:c}
      <span class="merge-line muted">${n.carrier}</span>
      ${o?l`<span class="merge-line muted" data-amazon-tracking>${o}</span>`:c}
      ${n.emails?l`<span class="merge-line muted">${n.emails}</span>`:c}
      <span class="merge-line items ${n.items?"":"muted"}">
        ${n.items??n.noItems}
      </span>
      ${i?l`<span class="merge-line items" data-also>${i}</span>`:c}
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
      <p class="hint" id="split-hint">${s.splitHint}</p>`}_renderActions(e){let r=this._busy?"true":"false",n=l`<button type="button" class="btn" data-cancel @click=${this._backToView}>
      ${s.cancel}
    </button>`;switch(this._mode){case"date":return l`<div class="dialog-actions">
          ${n}
          <button type="submit" form="date-form" class="btn primary" aria-disabled=${r}>
            ${s.save}
          </button>
        </div>`;case"merge":{let{pool:i,target:o}=this._mergeChoice(e);return l`<div class="dialog-actions">
          ${n}
          ${i.likely.length+i.older.length?l`<button
                type="button"
                class="btn primary"
                aria-disabled=${this._busy||!o?"true":"false"}
                @click=${this._merge}
              >
                ${s.mergeConfirm}
              </button>`:c}
        </div>`}case"split":{let i=lr(this._splitChosen,this._splitRows.length);return l`<div class="dialog-actions">
          ${n}
          <button
            type="button"
            class="btn primary"
            aria-disabled=${this._busy||!i?"true":"false"}
            @click=${this._split}
          >
            ${s.splitConfirm}
          </button>
        </div>`}case"archive":return l`<div class="dialog-actions">
          ${n}
          <button
            type="button"
            class="btn primary danger"
            aria-disabled=${r}
            @click=${this._archive}
          >
            ${s.archive}
          </button>
        </div>`;default:{let i=this._splitRows.length>=2;return l`<div class="dialog-actions" role="group" aria-label=${s.actions}>
          <button type="button" class="btn" data-mode="date" @click=${this._editDate}>
            ${s.editDate}
          </button>
          ${Ui(e,this.snapshot?.settings.user_is_admin===!0)?l`<button
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
          ${i?l`<button type="button" class="btn" data-mode="split" @click=${this._startSplit}>
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
          ${Pe(e.status)?l`<span class="spacer"></span>
                <button
                  type="button"
                  class="btn"
                  aria-disabled=${r}
                  @click=${this._markDelivered}
                >
                  <ha-icon icon="mdi:check" aria-hidden="true"></ha-icon>${s.markDelivered}
                </button>`:c}
        </div>`}}}_setMode(e){this._mode=e,this._error=null,this._formError=null,this.focusAfterRender(e==="archive"?"[data-cancel]":"[data-first], [data-cancel]")}_backToView(){let e=this._mode;this._mode="view",this._error=null,this._formError=null,this.focusAfterRender(`[data-mode="${e}"]`)}_editDate(){let e=this._parcel;this._dateForm=e?Mn(e):us,this._setMode("date")}_startMerge(){this._mergeTarget="",this._mergeQuery="",this._mergeOlder=!1,this._mergeHint=!1,this._setMode("merge")}_startSplit(){this._splitSelection=[],this._setMode("split")}_startArchive(){this._setMode("archive")}_parcelService(e,r,n){let i=this.hass,o=this._parcel;!i||!o||this.runAction(()=>V(i,e,{parcel_id:o.id,...r}),n)}_confirm(){this._parcelService("update",{confirm:!0})}_undoMerge(){this._parcelService("undo_merge",{})}_keepMerge(){this._parcelService("update",{confirm_merge:!0})}_undoDelivery(){this._parcelService("undo_delivery",{})}_keepInferred(){this._parcelService("update",{confirm_delivery:!0})}_markDelivered(){this._parcelService("mark_delivered",{})}async _checkAgain(){let e=this.hass,r=this._parcel;if(!e||!r||this._busy)return;let n=++this._checkRun,i=xr(null);this._checkStatus=null,this._checking=!0,await this.runAction(async()=>{let o=await K(e,"parcel/check_again",{parcel_id:r.id});i=xr(o)},()=>{let o=this.snapshot?.settings;this._checkStatus=zi(i,{enabled:o?.ai_enabled===!0,mode:o?.ai_mode??"off"})}),n===this._checkRun&&(this._checking=!1)}_dismissCheckStatus(){this._checkStatus=null}_archive(){this._parcelService("archive",{},()=>this.closeDialog())}_onPrivateClick(e){this._busy&&e.preventDefault()}_togglePrivate(e){let r=e.currentTarget.checked,n=this.hass,i=this._parcel;!n||!i||this._busy||(this._pendingPrivate=r,this.runAction(async()=>{try{await V(n,"update",{parcel_id:i.id,private:r})}catch(o){throw this._pendingPrivate=null,o}}))}_onDateInput(e){let r=e.currentTarget,n=r.name;this._dateForm={...this._dateForm,[n]:r.value},this._formError=null}_saveDate(e){e.preventDefault();let r=this._parcel;if(!r||this._busy)return;let n=this._dateForm,i=St(n);if(i){this._formError=i,this.focusAfterRender(`[name="${i.field}"]`);return}let o=Nn(r.id,n);this._parcelService("update",o,()=>this._backToView())}_mergePool(e){let r=this.snapshot;if(!r)return{likely:[],older:[]};let n=new Set([...this._ruledOut(e.id),...this._pointsElsewhere(e.id)]);return ai(r.parcels,e,this._dayContext(),n)}_ruledOut(e){let r=this._details;return new Set(r?.parcel.id===e?r.contradicted:[])}_pointsElsewhere(e){let r=this._details;return new Set(r?.parcel.id===e?r.elsewhere:[])}_mergeChoice(e){let r=this._mergePool(e),n=this._mergeQuery.trim(),i=r.likely;n?i=di([...r.likely,...r.older],n):this._mergeOlder&&(i=[...r.likely,...r.older]);let o=i.some(a=>a.id===this._mergeTarget)?this._mergeTarget:"";return{pool:r,shown:i,target:o}}_onMergeTarget(e){this._mergeTarget=e.currentTarget.value,this._mergeHint=!1}_onMergeQuery(e){this._mergeQuery=e.currentTarget.value}_showOlderMerge(){this._mergeOlder=!0,this.focusAfterRender("[data-older-first]")}_acceptPossible(e){let r=this.hass;if(!r)return;let n=null;this.runAction(async()=>{let i=await K(r,"suggestion/accept",{suggestion_id:e.suggestionId,parcel_id:e.candidateId});n=typeof i?.parcel_id=="string"?i.parcel_id:null},()=>{n!==null&&n!==this._parcelId&&(this._parcelId=n,this._details=null,this._loadError=null,this._load()),this.focusAfterRender("[data-autofocus]")})}_dismissPossible(e){let r=this.hass;r&&this.runAction(()=>K(r,"suggestion/dismiss",{suggestion_id:e.suggestionId,parcel_id:e.candidateId}),()=>{this.focusAfterRender("[data-autofocus]")})}_merge(){let e=this.hass,r=this._parcel;if(!e||!r)return;let{target:n}=this._mergeChoice(r);if(!n){this._mergeHint=!0,this.focusAfterRender('input[name="merge-target"]');return}this.runAction(()=>V(e,"merge",{parcel_ids:[r.id,n]}),()=>this._backToView())}_onSplitChange(e){let r=e.currentTarget,n=this._splitSelection.filter(i=>i!==r.value);this._splitSelection=r.checked?[...n,r.value]:n}_split(){let e=this._splitRows,r=this._splitChosen;lr(r,e.length)&&this._parcelService("split",{origins:ts(e,r)},()=>this._backToView())}_onOriginsToggle(e){this._originsOpen=e.currentTarget.open}_toggleFold(e){let r=new Set(this._openFolds);r.delete(e)||r.add(e),this._openFolds=r}_dismissOriginNotice(){this._originNotice=null}_showParcel(e){e!==null&&this._switchTo(e)}async _focusOrigins(){if(await this.updateComplete,!this.isOpen)return;let e=this.renderRoot.querySelector("dialog [data-origins-summary]");e?e.focus():this.focusInDialog("[data-autofocus]")}_moveRow(e){let r=this.hass,n=this._parcel;if(!r||!n||this._busy)return;let i=n.id,o=null;this._originNotice=null,this.runAction(async()=>{o=await vn(r,"split",{parcel_id:i,origins:e.ids})},()=>{let a=o;this._originNotice={text:s.movedNotice,undo:a===null?null:()=>this._moveBack(i,a),show:a},this._load(),this._focusOrigins()})}_moveBack(e,r){let n=this.hass;!n||this._busy||this.runAction(()=>V(n,"merge",{parcel_ids:[e,r]}),()=>{this._originNotice={text:s.movedBackNotice,undo:null,show:null},this._load(),this._focusOrigins()})}_removeRow(e){let r=this.hass,n=this._parcel;if(!r||!n||this._busy)return;let i=n.id,o=null,a=!0;this._originNotice=null,this.runAction(async()=>{let d=await K(r,"origin/remove",{parcel_id:i,origin_id:e.lead});o=typeof d?.filtered_id=="string"?d.filtered_id:null,a=typeof d?.parcel_id=="string"},()=>{let d=o;this._originNotice={text:a?s.removedNotice:s.removedGoneNotice,undo:d===null?null:()=>this._restoreRow(d,i),show:null},a&&this._load(),this._focusOrigins()})}_restoreRow(e,r){let n=this.hass;if(!n||this._busy)return;let i=null,o=[];this.runAction(async()=>{let a=await K(n,"review/restore",{filtered_id:e});i=typeof a?.review_id=="string"?a.review_id:null;let d=a?.parcel_ids;o=Array.isArray(d)?d.filter(u=>typeof u=="string"):[]},()=>{let a=this._parcelId===r&&!this.snapshot?.parcels.some(u=>u.id===r),d=ns({review:i,parcels:o},r,a);d.follow!==null&&(this._parcelId=d.follow,this._details=null,this._loadError=null),this._originNotice={text:ba[d.notice],undo:null,show:d.show},this._load(),this._focusOrigins()})}async _copy(e){let r=e.currentTarget,n=this._parcel?.tracking_number?.trim();if(!n)return;this._copyState="idle";try{if(!navigator.clipboard?.writeText)throw new Error("Clipboard API unavailable");await navigator.clipboard.writeText(n),this._copyState="copied";return}catch{}let i=this.renderRoot.querySelector("#tracking-number");i?.focus(),i?.select();let o=!1;try{o=document.execCommand("copy")}catch{o=!1}this._copyState=o?"copied":"failed",o&&r.focus()}};W("parcels-details-dialog",Sr);function Rr(t,e){let r=I(t.status_time,e.timeZone);switch(t.status){case"cancelled":return null;case"delivered":{let o=I(t.delivered_at,e.timeZone)??r;return o?{kind:"delivered",from:o,to:o}:null}case"returned":return r?{kind:"returned",from:r,to:r}:null;case"ready_for_pickup":{let o=r??e.today;return{kind:"pickup",from:o,to:In(o,e.today)}}default:break}let{today:n}=e,i=M(t);return i?!t.archived&&w(i.end,n)<0?{kind:"late",from:n,to:n,expected:i.end}:{kind:"eta",from:i.start,to:i.end}:(t.status==="attempted"||t.status==="exception")&&r?!t.archived&&w(r,n)<0?{kind:"late",from:n,to:n,expected:r,since:!0}:{kind:"status",from:r,to:r}:null}function Ht(t){return t.type==="parcel"?t.parcel.id:`return:${t.ret.id}`}function de(t){return t.type==="parcel"&&t.placement.kind==="late"}function ps(t){return t.window_start??t.window_end??"~"}function at(t,e){return t<e?-1:t>e?1:0}function wa(t,e){return at(ps(t.parcel),ps(e.parcel))||at(O(t.parcel).toLowerCase(),O(e.parcel).toLowerCase())||at(t.parcel.id,e.parcel.id)}function ka(t,e){return at(we(t.ret).toLowerCase(),we(e.ret).toLowerCase())||at(t.ret.id,e.ret.id)}function $a(t,e){let r=t.startCol-e.startCol||Number(de(e))-Number(de(t))||e.endCol-e.startCol-(t.endCol-t.startCol)||(t.type===e.type?0:t.type==="parcel"?-1:1);return r||(t.type==="parcel"&&e.type==="parcel"?wa(t,e):t.type==="return"&&e.type==="return"?ka(t,e):0)}function Tr(t,e,r,n,i=[]){let o=Ln(e),a=ae(e,6),d=[];for(let m of t){if(m.archived&&!n.showArchived)continue;let _=Rr(m,r);!_||w(_.to,e)<0||w(_.from,a)>0||d.push({type:"parcel",parcel:m,members:[m],placement:_,startCol:Math.max(0,ee(e,_.from)),endCol:Math.min(6,ee(e,_.to)),continuesBefore:w(_.from,e)<0,continuesAfter:w(_.to,a)>0,lane:0})}let u=br(d,m=>vr(m.parcel,m.placement.kind,m.placement.from,m.placement.to,m.placement.expected??"",m.placement.since?"since":"")).map(m=>({...m.reduce((f,v)=>Ue(v.parcel,f.parcel)<0?v:f),members:m.map(f=>f.parcel).sort(Ue)}));for(let m of i){if(m.archived&&!n.showArchived||w(m.day,e)<0||w(m.day,a)>0)continue;let _=ee(e,m.day);u.push({type:"return",ret:m,day:m.day,startCol:_,endCol:_,continuesBefore:!1,continuesAfter:!1,lane:0})}u.sort($a);let p=[];for(let m of[...u.filter(de),...u.filter(_=>!de(_))]){let _=o.map((v,$)=>$).slice(m.startCol,m.endCol+1),f=p.find(v=>_.every($=>!v[$]));f||(f=o.map(()=>!1),p.push(f));for(let v of _)f[v]=!0;m.lane=p.indexOf(f)}let g=o.map((m,_)=>u.filter(f=>f.startCol<=_&&_<=f.endCol).sort((f,v)=>f.lane-v.lane));return{start:e,end:a,days:o,items:u,lanes:p.length,perDay:g,busy:g.map(m=>m.length>0)}}function hs(t,e){return Tr(t,Te(e.today),e,{showArchived:!1}).items.filter(de)}var Ar=["all","active","recent","completed"],Ut={all:s.filterAll,active:s.filterActive,recent:s.filterRecent,completed:s.filterCompleted},zt="parcels-filter",Bt="parcels-filter-changed";function Er(t){return typeof t=="string"&&Ar.includes(t)}function ms(){try{return globalThis.localStorage??null}catch{return null}}function jt(t=ms()){try{let e=t?.getItem(zt);return Er(e)?e:"all"}catch{return"all"}}function fs(t,e=ms(),r=globalThis.window??null){try{e?.setItem(zt,t)}catch{}r?.dispatchEvent(new CustomEvent(Bt,{detail:t}))}function xa(t,{today:e,timeZone:r}){let n=Te(e),i=ae(n,6),o=d=>d!==null&&w(d,n)>=0&&w(d,i)<=0;if(o(I(t.status_time,r))||o(I(t.delivered_at,r))||Rr(t,{today:e,timeZone:r})?.kind==="late")return!0;let a=M(t);return a!==null&&w(a.start,i)<=0&&w(a.end,n)>=0}function gs(t,e,r){switch(e){case"active":return Pe(t.status);case"completed":return!Pe(t.status);case"recent":return xa(t,r);default:return!0}}function _s(t,e,{today:r}){switch(e){case"active":return!ye(t,r);case"completed":return ye(t,r);case"recent":{let n=Te(r);return w(t.day,n)>=0&&w(t.day,ae(n,6))<=0}default:return!0}}var Pr=class extends me{static properties={snapshot:{attribute:!1},locale:{attribute:!1},_returnId:{state:!0},_mode:{state:!0}};static styles=[q,Ne,T`
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
    `];constructor(){super(),this.snapshot=null,this.locale=De(void 0),this._returnId=null,this._mode="view"}async open(e,r=null){this._returnId=e,this._mode="view",await this.showDialog(r)}dialogClosed(){this._returnId=null,this._mode="view"}canLightDismiss(){return this._mode==="view"&&!this._busy}get _return(){let e=this._returnId;return e===null?null:this.snapshot?.returns.find(r=>r.id===e)??null}renderContent(){let e=this._return,r=this.snapshot?.settings.today??"";return l`
      <div class="dialog-header">
        <div class="dialog-heading">
          <h2 id="dialog-title" class="dialog-title">
            ${e?we(e):s.returnDetails}
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
      ${e?this._renderActions(e,r):c}
    `}_renderBadges(e,r){return l`<div class="dialog-badges">
      <span class="badge return">
        <ha-icon icon=${ze} aria-hidden="true"></ha-icon>${st(e,r)}
      </span>
      ${e.private||e.restricted?l`<span class="badge">
            <ha-icon icon="mdi:lock" aria-hidden="true"></ha-icon>${s.private}
          </span>`:c}
      ${e.archived?l`<span class="badge">${s.archived}</span>`:c}
    </div>`}_renderBody(e){return e?this._mode==="remove"?l`<p>${s.removeReturnQuestion}</p>`:l`<p class="hint">${s.returnHint}</p>
      ${this._renderFacts(e)}`:l`<p class="empty">${s.returnNotFound}</p>`}_renderFacts(e){let r=this.locale,n=(p,g)=>l`<div><dt>${p}</dt><dd>${g}</dd></div>`,i=yr(e.pickup_rule),o=e.restricted?null:R(e),a=e.restricted?null:Ft(e.tracking_url),d=e.tracking_number?.trim()??"",u=this._parcels(e);return l`<dl class="facts">
      ${e.pickup?n(s.pickup,l`${A(e.pickup,r)}${i?l`<div class="hint">${i}</div>`:c}`):c}
      ${e.picked_up?n(s.returnPickedUpAt,E(e.picked_up,r)):c}
      ${e.started?n(s.returnStartedDay,E(e.started,r)):c}
      ${o||a?n(s.returnCarrier,l`${o??""}${a?l`<a class="link" href=${a} target="_blank" rel="noopener noreferrer">
                  ${s.trackOnline}<span class="sr-only"> ${s.opensInNewTab}</span>
                  <ha-icon icon="mdi:open-in-new" aria-hidden="true"></ha-icon>
                </a>`:c}`):c}
      ${d?n(s.trackingNumber,d):c}
      ${e.order_numbers.length?n(s.orders,e.order_numbers.join(", ")):c}
      ${e.items.length?n(s.items,l`<ul>
              ${e.items.map(p=>l`<li>${p}</li>`)}
            </ul>`):c}
      ${u.length?n(s.returnSentBackFrom,l`<ul>
              ${u.map(p=>this._renderParcel(p))}
            </ul>`):c}
      ${e.emails.length?n(s.returnEmails,this._renderEmails(e)):c}
      ${e.restricted?c:n(s.returnId,e.id)}
    </dl>`}_parcels(e){let r=this.snapshot?.parcels??[];return e.parcel_ids.flatMap(n=>r.find(i=>i.id===n)??[])}_renderParcel(e){let r=O(e),n=e.delivered_undated?e.delivered_timeless&&z(e.delivered_at,this.locale,fe)||s.dateNotKnownInline:e.delivered_at?E(e.delivered_at,this.locale):"",i=[H(e.status),n].filter(Boolean).join(" \xB7 ");return e.restricted?l`<li>${r} · ${i}</li>`:l`<li>
      <button
        type="button"
        class="link-btn"
        aria-haspopup="dialog"
        aria-label=${h(s.showParcel,{name:r})}
        aria-disabled=${this._busy?"true":"false"}
        @click=${()=>this._openParcel(e.id)}
      >
        ${r}</button
      > · ${i}
    </li>`}_renderEmails(e){let r=this.locale;return l`<ul class="emails">
      ${e.emails.map(n=>{let i=n.label.trim(),o=[n.time?E(n.time,r):"",Ee(n.source)].filter(Boolean).join(" \xB7 ");return l`<li>
          ${i?l`<div>${i}</div>`:c}
          <div class="entry-meta">${o}</div>
        </li>`})}
    </ul>`}_renderActions(e,r){let n=this._busy?"true":"false",i=!e.restricted&&this.snapshot?.settings.user_is_admin===!0;if(this._mode==="remove"&&i)return l`<div class="dialog-actions">
        <button type="button" class="btn" data-cancel @click=${this._backToView}>
          ${s.cancel}
        </button>
        <button
          type="button"
          class="btn primary danger"
          aria-disabled=${n}
          @click=${this._remove}
        >
          ${s.removeReturn}
        </button>
      </div>`;let o=Li(e,r),a=Ii(e,r);return!i&&!o&&!a?c:l`<div class="dialog-actions" role="group" aria-label=${s.actions}>
      ${i?l`<button type="button" class="btn danger" data-mode="remove" @click=${this._startRemove}>
            ${s.removeReturn}
          </button>`:c}
      <span class="spacer"></span>
      ${a?l`<button
            type="button"
            class="btn"
            aria-label=${h(s.undoPickedUpLabel,{title:we(e)})}
            aria-disabled=${n}
            @click=${()=>this._markPickedUp(!1)}
          >
            ${s.undo}
          </button>`:c}
      ${o?l`<button
            type="button"
            class="btn primary"
            aria-disabled=${n}
            @click=${()=>this._markPickedUp(!0)}
          >
            <ha-icon icon="mdi:check" aria-hidden="true"></ha-icon>${s.markPickedUp}
          </button>`:c}
    </div>`}_markPickedUp(e){let r=this.hass,n=this._return;if(!r||!n)return;let i=e?"mark_return_picked_up":"undo_return_picked_up";this.runAction(()=>V(r,i,{return_id:n.id}))}_startRemove(){this._mode="remove",this._error=null,this.focusAfterRender("[data-cancel]")}_backToView(){this._mode="view",this._error=null,this.focusAfterRender('[data-mode="remove"]')}_remove(){let e=this.hass,r=this._return;!e||!r||this.runAction(()=>K(e,"return/remove",{return_id:r.id}),()=>this.closeDialog())}_openParcel(e){this._busy||(this.closeDialog(),this.dispatchEvent(new CustomEvent(En,{detail:e})))}};W("parcels-return-dialog",Pr);var Sa="parcels/subscribe",bs=[2e3,1e4,3e4,6e4,3e5],Kt=new Map,Ra=0;function ys(t,e){try{t(e)}catch(r){console.error(r)}}function vs(t,e){t.state=e;for(let r of[...t.listeners.values()])ys(r,e)}function ws(t){try{t().catch(()=>{})}catch{}}function qt(t){t.retryTimer!==void 0&&(clearTimeout(t.retryTimer),t.retryTimer=void 0)}function Wt(t){t.connection.removeEventListener("ready",t.onReady),t.connection.removeEventListener("disconnected",t.onDisconnected)}function Ta(t){qt(t);let e=bs[Math.min(t.retries,bs.length-1)]??3e5;t.retries+=1,t.retryTimer=setTimeout(()=>{t.retryTimer=void 0,Cr(t)},e)}function Cr(t){if(t.released||t.unsubscribe||t.pending||t.listeners.size===0)return;qt(t);let e=++t.attempt,r=t.epoch,n=()=>!t.released&&t.attempt===e;t.pending=!0;let i;try{i=t.connection.subscribeMessage(o=>{n()&&(t.retries=0,vs(t,{snapshot:Qi(o),error:null}))},{type:Sa},{resubscribe:!1})}catch(o){i=Promise.reject(o)}i.then(o=>{if(n()){t.pending=!1,t.unsubscribe=o;return}t.epoch===r&&ws(o),t.released&&t.attempt===e+1&&(t.pending=!1,Wt(t))},o=>{n()?(t.pending=!1,vs(t,{snapshot:t.state.snapshot,error:Y(o)}),Ta(t)):t.released&&t.attempt===e+1&&(t.pending=!1,Wt(t))})}function Aa(t,e){if(!t.listeners.delete(e)||t.listeners.size>0)return;t.released=!0,t.attempt+=1,qt(t),Kt.get(t.connection)===t&&Kt.delete(t.connection);let r=t.unsubscribe;t.unsubscribe=null,r&&ws(r),t.pending||Wt(t)}function Ea(t){let e={connection:t,listeners:new Map,state:{snapshot:null,error:null},epoch:0,attempt:0,unsubscribe:null,pending:!1,released:!1,retries:0,retryTimer:void 0,onReady:()=>{e.released||e.unsubscribe||(e.pending=!1,e.retries=0,Cr(e))},onDisconnected:()=>{e.epoch+=1,e.attempt+=1,e.unsubscribe=null,e.pending=!1,qt(e),e.released&&Wt(e)}};return e}function ks(t,e){let r=++Ra,n=Kt.get(t);n?(n.listeners.set(r,e),(n.state.snapshot||n.state.error)&&ys(e,n.state)):(n=Ea(t),Kt.set(t,n),n.listeners.set(r,e),t.addEventListener("ready",n.onReady),t.addEventListener("disconnected",n.onDisconnected),Cr(n));let i=n,o=!0;return()=>{o&&(o=!1,Aa(i,r))}}var Gt=class{snapshot=null;error=null;_host;_connection=null;_unsubscribe=null;_hostConnected=!1;constructor(e){this._host=e,e.addController(this)}setConnection(e){e!==this._connection&&(this._release(),this._connection=e,this.snapshot=null,this.error=null,this._hostConnected&&this._subscribe(),this._host.requestUpdate())}hostConnected(){this._hostConnected=!0,this._subscribe()}hostDisconnected(){this._hostConnected=!1,this._release()}_subscribe(){!this._connection||this._unsubscribe||(this._unsubscribe=ks(this._connection,e=>{this.snapshot=e.snapshot??this.snapshot,this.error=e.error,this._host.requestUpdate()}))}_release(){let e=this._unsubscribe;this._unsubscribe=null,e?.()}};var lt=class extends Z{static properties={_actionError:{state:!0}};_snapshots=new Gt(this);_hass=void 0;_hassKey=null;_locale=null;_localeKey="";constructor(){super(),this._actionError=null}get hass(){return this._hass}set hass(e){this._hass=e,this._snapshots.setConnection(e?.connection??null),this.toggleAttribute("dark",e?.themes?.darkMode===!0);let r=JSON.stringify([e?.language,e?.locale?.language,e?.locale?.time_format,e?.locale?.time_zone,e?.config?.time_zone,e?.user?.is_admin,e?.themes?.darkMode]);r!==this._hassKey&&(this._hassKey=r,this.requestUpdate()),this.hassChanged()}hassChanged(){}get snapshot(){return this._snapshots.snapshot}get locale(){let e=this._snapshots.snapshot?.settings.time_zone,r=`${this._hassKey??""}|${e??""}`;return(!this._locale||r!==this._localeKey)&&(this._locale=De(this._hass,e),this._localeKey=r),this._locale}async callService(e,r,n){let i=this._hass;if(!i)return!1;this._actionError=null;try{return await V(i,e,r),!0}catch(o){return this._actionError=h(n,{message:Y(o)}),!1}}renderBanners(){let{snapshot:e,error:r}=this._snapshots;return!r&&!this._actionError?c:l`<div class="banners">
      ${r?l`<div class="alert ${e?"warning":"error"}" role="alert">
            <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              ${h(e?s.refreshError:s.loadError,{message:r})}
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
    </div>`}renderLoading(){return this._snapshots.error?c:l`<p class="empty" role="status">${s.loading}</p>`}showActionError(e){this._actionError=e}_dismissActionError(){this._actionError=null}},Be=class extends lt{static properties={_busyParcels:{state:!0},_filter:{state:!0}};_focusedParcel=null;_focusedReturn=null;constructor(){super(),this._busyParcels=new Set,this._filter=jt()}connectedCallback(){super.connectedCallback(),this._filter=jt(),window.addEventListener(Bt,this._onFilterEvent),window.addEventListener("storage",this._onStorage),window.addEventListener("location-changed",this._onLocationChanged),window.addEventListener("popstate",this._onLocationChanged)}disconnectedCallback(){super.disconnectedCallback(),window.removeEventListener(Bt,this._onFilterEvent),window.removeEventListener("storage",this._onStorage),window.removeEventListener("location-changed",this._onLocationChanged),window.removeEventListener("popstate",this._onLocationChanged)}setFilter(e){this._filter=e,fs(e)}filterParcels(e,r){let n=this._filter;if(n==="all")return r;let i={today:e.settings.today,timeZone:e.settings.time_zone};return r.filter(o=>gs(o,n,i))}filterReturns(e,r){let n=this._filter;if(n==="all")return r;let i={today:e.settings.today};return r.filter(o=>_s(o,n,i))}_candidates=null;possiblyFor(e){let r=this.snapshot;if(!r)return null;this._candidates?.snapshot!==r&&(this._candidates={snapshot:r,map:ci(r.merge_suggestions)});let n=this._candidates.map,i=new Set(e.map(a=>a.id)),o=new Map;for(let a of e)for(let d of n.get(a.id)??[])i.has(d.id)||o.set(d.id,d);return o.size?xi([...o.values()]):null}_onFilterEvent=e=>{let r=e.detail;Er(r)&&(this._filter=r)};_onStorage=e=>{(e.key===null||e.key===zt)&&(this._filter=jt())};_onLocationChanged=()=>{this._openLinked()};_openLinked(){let e=this.snapshot;if(!e||!this.isConnected)return;let{pathname:r,search:n,hash:i}=window.location,o=cs(n);if(o===n)return;window.history.replaceState(window.history.state,"",`${r}${o}${i}`);let a=ds(n);if(a?.kind==="parcel"){let d=e.parcels.find(u=>u.id===a.id);d&&this.openDetails(d,null)}else if(a?.kind==="return"){let d=e.returns.find(u=>u.id===a.id);d&&this.openReturn(d,null)}}willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement,n=r instanceof HTMLElement?r.closest(".chip"):null;this._focusedParcel=n?.dataset.parcelId??null,this._focusedReturn=n?.dataset.returnId??null}updated(e){super.updated(e),this._restoreFocus(),this._openLinked()}_restoreFocus(){let e=this._focusedParcel,r=this._focusedReturn;if(this._focusedParcel=null,this._focusedReturn=null,this.shadowRoot?.activeElement||!Lr())return;let n=e!==null?kr(e):r!==null?$r(r):null;n&&this.renderRoot.querySelector(n)?.focus()}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback], button.chip-main")}openDetails=(e,r)=>{this.renderRoot.querySelector("parcels-details-dialog")?.open(e.id,()=>{(r?.isConnected?r:this.renderRoot.querySelector(kr(e.id))??this.focusFallback())?.focus()})};openReturn=(e,r)=>{this.renderRoot.querySelector("parcels-return-dialog")?.open(e.id,()=>{(r?.isConnected?r:this.renderRoot.querySelector($r(e.id))??this.focusFallback())?.focus()})};undoMerge=e=>{this._parcelAction(e.id,"undo_merge",{parcel_id:e.id},s.undoFailed)};keepMerge=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_merge:!0},s.keepFailed)};undoInferred=e=>{this._parcelAction(e.id,"undo_delivery",{parcel_id:e.id},s.undoInferredFailed)};keepInferred=e=>{this._parcelAction(e.id,"update",{parcel_id:e.id,confirm_delivery:!0},s.keepInferredFailed)};renderDetailsDialog(){return l`<parcels-details-dialog
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
    ></parcels-return-dialog>`}_opener(){let e=this.shadowRoot?.activeElement;return e instanceof HTMLElement?e:this.focusFallback()}_onOpenParcel(e){let r=this.snapshot?.parcels.find(i=>i.id===e.detail),n=this._opener();r&&n&&this.openDetails(r,n)}_onOpenReturn(e){let r=this.snapshot?.returns.find(i=>i.id===e.detail),n=this._opener();r&&n&&this.openReturn(r,n)}async _parcelAction(e,r,n,i){if(!this._busyParcels.has(e)){this._busyParcels=new Set([...this._busyParcels,e]);try{await this.callService(r,n,i)}finally{let o=new Set(this._busyParcels);o.delete(e),this._busyParcels=o}}}_onDialogError(e){this.showActionError(e.detail)}};function Lr(){let t=document.activeElement;return!t||t===document.body}function Ir(t){if(typeof t!="object"||t===null||Array.isArray(t))throw new Error(s.configInvalid);return t}function Or(t){let e=t.title;if(e!=null){if(typeof e!="string")throw new Error(s.configTitle);return e.trim()}}function Mr(t){return typeof t.type=="string"?t.type:""}function Nr(t){let e=Ir(t),r=e.show_archived??!0;if(typeof r!="boolean")throw new Error(s.configShowArchived);return{type:Mr(e),title:Or(e),show_archived:r}}function Dr(t){let e=Ir(t);return{type:Mr(e),title:Or(e)}}function Fr(t){let e=Ir(t);return{type:Mr(e),title:Or(e)}}function je(t,e){return t===void 0?e:t||null}function Hr(t,e,r){let n=t.get(e);return n==="pending"||n!==void 0&&n===r}function Vt(t,e,r){if(!e.size)return t;let n=t.filter(i=>!Hr(e,i.id,r));return n.length===t.length?t:n}function Ur(t,e){let r=new Map(t);for(let n of e)r.set(n,"pending");return r}function zr(t,e){let r=new Map(t);for(let n of e)r.delete(n);return r}function Br(t,e,r,n){let i=new Map(t);for(let o of e)r&&n(o)?i.set(o,r):i.delete(o);return i}function xs(t,e){let r=null;for(let[n,i]of t)i!=="pending"&&i!==e&&(r??=new Map(t),r.delete(n));return r??t}function Ss(t,e){if(t<=0)return null;let r=t===1?s.aiQueueOne:h(s.aiQueueMany,{count:t});if(e===null)return r;let n=Math.max(1,Math.round(e/60));return n<120?h(s.aiQueueMinutes,{queue:r,minutes:n}):h(s.aiQueueHours,{queue:r,hours:Math.round(n/60)})}function Ke(t,e,r){return t<=0?null:t===1?e:h(r,{count:t})}function Rs(t){let e=[Ke(t.added,s.trustAddedOne,s.trustAddedMany),Ke(t.rechecking,s.trustRecheckOne,s.trustRecheckMany),Ke(t.kept,s.trustKeptOne,s.trustKeptMany)].filter(r=>r!==null);return e.length?h(s.trustDoneWith,{domain:t.domain,parts:e.join(", ")}):h(s.trustDone,{domain:t.domain})}var $s=3;function Pa(t){return t.length<2?t[0]??"":h(s.listAnd,{list:t.slice(0,-1).join(", "),last:t.at(-1)??""})}function Ts(t){if(t.count<=0)return null;let e=t.count===1?s.unreadOne:h(s.unreadMany,{count:t.count});if(!t.senders.length)return`${e}.`;let r=t.senders.slice(0,$s),n=t.unnamed===1?s.unreadUnknownOne:s.unreadUnknownMany,i=t.senders.length>$s?[...r,s.unreadOthers]:t.unnamed>0?[...r,n]:r;return h(s.unreadFrom,{unread:e,senders:Pa(i)})}function As(t){let e=[Ke(t.read,s.retryReadOne,s.retryReadMany),Ke(t.failed,s.retryFailedOne,s.retryFailedMany),Ke(t.gone,s.retryGoneOne,s.retryGoneMany)].filter(r=>r!==null);return e.length?h(s.retryDoneWith,{parts:e.join(", ")}):s.retryNothing}function Es(t){let e=[[s.checkHeaders,String(t.headers)]];return t.servers.length&&e.push([s.checkServers,t.servers.map(r=>r||s.checkNoServer).join(", ")]),t.originals>0&&e.push([s.checkOriginals,String(t.originals)]),t.used===null?(e.push([s.checkUsed,s.checkUsedNone]),e):(e.push([s.checkUsed,h(s.checkUsedHeader,{n:t.used+1})],["DKIM",t.dkim||s.checkNoResult],["DMARC",t.dmarc||s.checkNoResult],["SPF",t.spf||s.checkNoResult]),e)}function Ps(t){let e=t.subject.trim();return e||(t.removed?s.removedFromParcel:s.noSubject)}var Yt="parcels-show-review";function Cs(t=globalThis.window??null){if(!t)return!1;let e=new CustomEvent(Yt,{cancelable:!0});return t.dispatchEvent(e),e.defaultPrevented}function Ls(t){return t.review.length+t.merge_suggestions.length+(t.unread_emails.count>0?1:0)}var Ca=600,La=616,Ia={weekday:"short"},Oa={day:"numeric"},Ma={weekday:"long",day:"numeric",month:"long"},Na={weekday:"long",day:"numeric",month:"short"},jr=class extends Be{static properties={_config:{state:!0},_weekOffset:{state:!0},_narrow:{state:!0},_refreshing:{state:!0}};static styles=[q,Rt,T`
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
      .attention {
        margin: 2px 0 0;
        font-size: 0.875rem;
        color: var(--primary-text-color, #212121);
      }
      .attention .link-btn {
        color: inherit;
      }
      .attention .link-btn:first-child {
        margin-inline-start: -4px;
      }
      .attention .late-link,
      .day.late-group .day-label {
        /* As the chips' "Late" line: at least 4.5:1, light and dark. */
        color: color-mix(in srgb, var(--error-color, #db4437) 40%, var(--primary-text-color, #212121));
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
    `];_resizeObserver=null;_resizeFrame=0;_layoutCache=null;_lateCache=null;constructor(){super(),this._config=Nr({}),this._weekOffset=0,this._narrow=!1,this._refreshing=!1}static getStubConfig(){return{}}setConfig(e){this._config=Nr(e)}getCardSize(){let e=this._layout();if(!e)return 4;if(this._narrow){let r=e.perDay.reduce((i,o)=>i+o.length,0);return 9+(e.items.some(de)?1:0)+r}return 3+Math.max(1,e.lanes)}getGridOptions(){return{columns:"full",rows:"auto",min_columns:6}}connectedCallback(){super.connectedCallback(),typeof ResizeObserver<"u"&&(this._resizeObserver??=new ResizeObserver(e=>{let r=e[e.length-1]?.contentRect.width??0;cancelAnimationFrame(this._resizeFrame),this._resizeFrame=requestAnimationFrame(()=>this._measure(r))}),this._resizeObserver.observe(this))}disconnectedCallback(){super.disconnectedCallback(),this._resizeObserver?.disconnect(),cancelAnimationFrame(this._resizeFrame)}firstUpdated(e){super.firstUpdated(e),this._measure(this.getBoundingClientRect().width)}focusFallback(){return this.renderRoot.querySelector("[data-focus-fallback]")}_measure(e){e<=0||(e<Ca?this._narrow=!0:e>=La&&(this._narrow=!1))}_monday(e){return ae(Te(e.settings.today),7*this._weekOffset)}_layout(){let e=this.snapshot;if(!e)return null;let r=this._monday(e),n=this._config.show_archived,i=this._filter,o=this._layoutCache;if(o&&o.snapshot===e&&o.monday===r&&o.showArchived===n&&o.filter===i)return o.layout;let a=Tr(this.filterParcels(e,e.parcels),r,{today:e.settings.today,timeZone:e.settings.time_zone},{showArchived:n},this.filterReturns(e,e.returns));return this._layoutCache={snapshot:e,monday:r,showArchived:n,filter:i,layout:a},a}render(){let e=this.snapshot,r=this._layout(),n=je(this._config.title,s.defaultWeekTitle),i=r?F(r.start,r.end,this.locale,Bn):"";return l`<ha-card>
        <div class="header">
          <div class="heading">
            ${n?l`<h2 class="title">${n}</h2>`:c}
            ${i?l`<p class="range" aria-live="polite">${i}</p>`:c}
            ${e?this._renderAttention(e):c}
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
        ${e&&r?this._narrow?this._renderStacked(e,r,i):this._renderGrid(e,r,i):l`<div class="content">${this.renderLoading()}</div>`}
      </ha-card>
      ${this.renderDetailsDialog()} ${this.renderReturnDialog()}
      <parcels-add-dialog
        .hass=${this.hass}
        @parcels-error=${this._onAddError}
      ></parcels-add-dialog>`}_renderAttention(e){let r=this._lateCount(e),n=e.settings.user_is_admin?Ls(e):0;if(r===0&&n===0)return c;let i=r?l`<button
          type="button"
          class="link-btn late-link"
          title=${s.attentionLateLabel}
          @click=${this._showLate}
        >
          ${h(s.attentionLate,{count:r})}
        </button>`:c,o=n?l`<button
          type="button"
          class="link-btn"
          title=${s.attentionReviewLabel}
          @click=${this._showReview}
        >
          ${n===1?s.attentionReviewOne:h(s.attentionReview,{count:n})}
        </button>`:c,a=r&&n?l`<span aria-hidden="true"> · </span>`:c;return l`<p class="attention">${i}${a}${o}</p>`}_lateCount(e){let r=this._filter,n=this._lateCache;if(n&&n.snapshot===e&&n.filter===r)return n.count;let i={today:e.settings.today,timeZone:e.settings.time_zone},o=hs(this.filterParcels(e,e.parcels),i).length;return this._lateCache={snapshot:e,filter:r,count:o},o}_showLate(){this._thisWeek(),this.updateComplete.then(()=>{let e=this.renderRoot.querySelector(".chip.late");e?.scrollIntoView?.({block:"nearest"}),e?.querySelector("button.chip-main")?.focus({preventScroll:!0})})}_showReview(){Cs()||this.showActionError(s.reviewCardMissing)}_renderGrid(e,r,n){let i=this.locale,o=e.settings.today,a=r.items.length===0,u={"grid-template-columns":r.busy.map(p=>p||a?"minmax(0, 1fr)":"minmax(0, 0.6fr)").join(" "),"grid-template-rows":`auto repeat(${Math.max(1,r.lanes)}, auto)`};return l`<div
      class="grid"
      role="group"
      aria-label=${h(s.weekOf,{range:n})}
      style=${j(u)}
    >
      ${r.days.map((p,g)=>l`<div
            class="day-bg ${p===o?"today":""}"
            style=${j({"grid-column":String(g+1)})}
            aria-hidden="true"
          ></div>`)}
      ${r.days.map((p,g)=>l`<div
            class="day-head ${p===o?"today":""}"
            style=${j({"grid-column":String(g+1)})}
            aria-current=${p===o?"date":c}
          >
            <span class="dow" aria-hidden="true">${A(p,i,Ia)}</span>
            <span class="dom" aria-hidden="true">${A(p,i,Oa)}</span>
            <span class="sr-only">${A(p,i,Ma)}</span>
          </div>`)}
      ${a?l`<p class="week-empty">${this._emptyText()}</p>`:c}
      ${X(r.items,Ht,p=>this._chip(p,!1,{"grid-column":`${p.startCol+1} / ${p.endCol+2}`,"grid-row":String(p.lane+2)}))}
    </div>`}_renderStacked(e,r,n){let i=this.locale,o=e.settings.today,a=this._filter!=="all"&&r.items.length===0;return l`${a?l`<p class="week-empty stacked">${this._emptyText()}</p>`:c}
      <ol class="days" aria-label=${h(s.weekOf,{range:n})}>
      ${r.days.map((d,u)=>{let p=r.perDay[u]??[],g=p.filter(de),m=g.length?p.filter(f=>!de(f)):p,_=d===o;return l`${g.length?this._renderLateGroup(g,u):c}<li
          class="day ${m.length?"":"compact"} ${_?"today":""}"
          aria-current=${_?"date":c}
        >
          <p class="day-label">
            ${A(d,i,Na)}${_?l`<span class="badge info">${s.todayTag}</span>`:c}
          </p>
          ${m.length?l`<ul class="day-chips">
                ${X(m,Ht,f=>l`<li>${this._chip(f,!0,void 0,u)}</li>`)}
              </ul>`:l`<span class="muted">${s.noDeliveriesThisDay}</span>`}
        </li>`})}
    </ol>`}_renderLateGroup(e,r){return l`<li class="day late-group">
      <p class="day-label">${s.lateGroup}</p>
      <ul class="day-chips">
        ${X(e,Ht,n=>l`<li>${this._chip(n,!0,void 0,r)}</li>`)}
      </ul>
    </li>`}_chip(e,r,n,i){if(e.type==="return")return Hi(e.ret,{locale:this.locale,today:this.snapshot?.settings.today??"",position:n,onOpen:this.openReturn});let o=e.continuesBefore&&(!r||i===e.startCol),a=e.continuesAfter&&(!r||i===e.endCol);return It(e.parcel,{locale:this.locale,placement:e.placement,continuesBefore:o,continuesAfter:a,showRange:r,members:e.members,possibly:this.possiblyFor(e.members),busy:e.members.some(d=>this._busyParcels.has(d.id)),position:n,onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge,onUndoInferred:this.undoInferred,onKeepInferred:this.keepInferred})}_renderFilters(){return l`<div class="filters" role="group" aria-label=${s.filterLabel}>
      ${Ar.map(e=>l`<button
            type="button"
            class="filter-btn"
            aria-pressed=${this._filter===e?"true":"false"}
            title=${e==="recent"?s.filterRecentHint:c}
            @click=${()=>this.setFilter(e)}
          >
            ${Ut[e]}
          </button>`)}
    </div>`}_emptyText(){return this._filter==="all"?s.noDeliveriesThisWeek:s.filterEmptyWeek}_previousWeek(){this._weekOffset-=1}_nextWeek(){this._weekOffset+=1}_thisWeek(){this._weekOffset=0}async _refresh(){if(!this._refreshing){this._refreshing=!0;try{await this.callService("refresh",{},s.refreshFailed)}finally{this._refreshing=!1}}}_openAdd(e){let r=e.currentTarget;this.renderRoot.querySelector("parcels-add-dialog")?.open(()=>{r.isConnected&&r.focus()})}_onAddError(e){this.showActionError(e.detail)}};W("parcels-week-card",jr);Me("parcels-week-card",s.weekCardName,s.weekCardDescription);var Kr=class extends Be{static properties={_config:{state:!0}};static styles=[q,Rt,T`
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
    `];_listCache=null;constructor(){super(),this._config=Dr({})}static getStubConfig(){return{}}setConfig(e){this._config=Dr(e)}getCardSize(){let e=this._list()?.boxes;return e?1+Math.max(1,e.length):3}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}focusFallback(){return this.renderRoot.querySelector("button.chip-main")??this.renderRoot.querySelector(".content")}_list(){let e=this.snapshot;if(!e)return null;let r=this._filter,n=this._listCache;if(n?.snapshot===e&&n.filter===r)return n;let i=ii(e.parcels),o=this.filterParcels(e,i);return this._listCache={snapshot:e,filter:r,boxes:Ti(o),hidden:i.length-o.length},this._listCache}render(){let e=this._list(),r=je(this._config.title,s.defaultListTitle);return l`<ha-card>
        ${r?l`<div class="header"><h2 class="title">${r}</h2></div>`:c}
        ${this.renderBanners()}
        <div class="content" tabindex="-1">
          ${e?this._renderList(e.boxes,e.hidden):this.renderLoading()}
        </div>
      </ha-card>
      ${this.renderDetailsDialog()} ${this.renderReturnDialog()}`}_renderFilterNote(e){return e===0||this._filter==="all"?c:l`<p class="filter-note">
      ${h(s.filterNote,{filter:Ut[this._filter]})} ·
      <button type="button" class="link-btn" @click=${this._showAll}>${s.filterShowAll}</button>
    </p>`}_showAll=()=>{this.setFilter("all")};_renderList(e,r){if(!e.length)return l`${this._renderFilterNote(r)}
        <p class="empty">${r>0?s.noUndatedMatch:s.noUndatedParcels}</p>`;let n=this.locale;return l`${this._renderFilterNote(r)}
      <ul class="list">
      ${X(e,i=>i.parcel.id,({parcel:i,members:o})=>l`<li>
            ${It(i,{locale:n,showStatus:!0,members:o,possibly:this.possiblyFor(o),busy:o.some(a=>this._busyParcels.has(a.id)),onOpen:this.openDetails,onUndoMerge:this.undoMerge,onKeepMerge:this.keepMerge,onUndoInferred:this.undoInferred,onKeepInferred:this.keepInferred})}
          </li>`)}
    </ul>`}};W("parcels-list-card",Kr);Me("parcels-list-card",s.listCardName,s.listCardDescription);var ce="unread-emails",We=["review","filtered"],Da=new Set(["not_parcel","unknown"]),Fa={weekday:"short",day:"numeric",month:"short"};function Is(t){return L(t.received??t.created)??-1/0}function Os(t){return[...t].sort((e,r)=>Is(r)-Is(e)||(e.id<r.id?-1:e.id>r.id?1:0))}function Ha(t){return[...t].sort((e,r)=>(r.day??"").localeCompare(e.day??"")||(e.id<r.id?-1:e.id>r.id?1:0))}function Wr(t,e){if(!t.has(e))return t;let r=new Map(t);return r.delete(e),r}var qr=class extends lt{static properties={_config:{state:!0},_tab:{state:!0},_editing:{state:!0},_editForm:{state:!0},_editProblem:{state:!0},_busyItems:{state:!0},_itemErrors:{state:!0},_hidden:{state:!0},_confirmClearAll:{state:!0},_confirmTrust:{state:!0},_status:{state:!0}};static styles=[q,T`
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
      .action-status .alert {
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
    `];connectedWhileHidden=!0;_focusedItem=null;_listCache=null;_visibleCache=null;_clearingAll=!1;constructor(){super(),this._config=Fr({}),this._tab="review",this._editing=null,this._editForm=ar(null),this._editProblem=null,this._busyItems=new Set,this._itemErrors=new Map,this._hidden=new Map,this._confirmClearAll=!1,this._confirmTrust=null,this._status=null}static getStubConfig(){return{}}setConfig(e){this._config=Fr(e)}getCardSize(){if(!this._visible())return 0;let e=this._visibleLists();if(!e)return 3;let r=this._tab==="review"?e.review.length+e.suggestions.length+(this._unreadEmails()?1:0):e.filtered.length;return 2+2*Math.max(1,r)}getGridOptions(){return{columns:12,rows:"auto",min_columns:6}}hassChanged(){this._syncVisibility()}connectedCallback(){super.connectedCallback(),window.addEventListener(Yt,this._onShowReview)}disconnectedCallback(){super.disconnectedCallback(),window.removeEventListener(Yt,this._onShowReview)}_onShowReview=e=>{e.defaultPrevented||!this._visible()||(e.preventDefault(),this._tab="review",this.scrollIntoView?.({block:"start"}),this.updateComplete.then(()=>this.renderRoot.querySelector("#tab-review")?.focus({preventScroll:!0})))};_visible(){let e=this.snapshot;return e?e.settings.user_is_admin:this.hass?.user?.is_admin===!0}_syncVisibility(){let e=!this._visible();this.hidden!==e&&(this.hidden=e,this.dispatchEvent(new CustomEvent("card-visibility-changed",{bubbles:!0,composed:!0,detail:{value:!e}})))}_lists(){let e=this.snapshot;return e?(this._listCache?.snapshot!==e&&(this._listCache={snapshot:e,review:Os(e.review),suggestions:Ha(e.merge_suggestions),filtered:Os(e.filtered)}),this._listCache):null}_visibleLists(){let e=this._lists();if(!e)return null;let r=this._hidden;if(this._visibleCache?.lists!==e||this._visibleCache.hidden!==r){let n=this.snapshot;this._visibleCache={lists:e,hidden:r,visible:{review:Vt(e.review,r,n),suggestions:Vt(e.suggestions,r,n),filtered:Vt(e.filtered,r,n)}}}return this._visibleCache.visible}_unreadEmails(){let e=this.snapshot;return e&&e.unread_emails.count>0&&!Hr(this._hidden,ce,e)?e.unread_emails:null}_listed(e){if(e===ce)return(this.snapshot?.unread_emails.count??0)>0;let r=this._lists();return r?[...r.review,...r.suggestions,...r.filtered].some(n=>n.id===e):!1}willUpdate(e){super.willUpdate(e);let r=this.shadowRoot?.activeElement,n=r instanceof HTMLElement?r.closest("[data-item-id]"):null;if(n){let o=[...this.renderRoot.querySelectorAll("[data-item-id]")].filter(a=>!a.closest("[hidden]"));this._focusedItem={id:n.dataset.itemId??"",index:o.indexOf(n)}}else this._focusedItem=null;this._hidden=xs(this._hidden,this.snapshot),this._confirmClearAll&&!this._visibleLists()?.filtered.length&&(this._confirmClearAll=!1,r instanceof HTMLElement&&r.closest(".confirm")&&this._focusAfterUpdate("#panel-filtered"));let i=this._lists();if(i){let o=new Set([...i.review,...i.suggestions,...i.filtered].map(a=>a.id));this._listed(ce)&&o.add(ce),this._editing!==null&&!o.has(this._editing)&&(this._editing=null,this._editProblem=null);for(let a of this._itemErrors.keys())o.has(a)||(this._itemErrors=Wr(this._itemErrors,a))}}updated(e){super.updated(e),this._syncVisibility();let r=this._focusedItem;if(this._focusedItem=null,!r||this.shadowRoot?.activeElement||!Lr())return;let i=[...this.renderRoot.querySelector(`#panel-${this._tab}`)?.querySelectorAll("[data-item-id]")??[]];(i.find(a=>a.dataset.itemId===r.id)??i[Math.min(Math.max(r.index,0),i.length-1)]??this.renderRoot.querySelector(`#tab-${this._tab}`))?.focus()}render(){if(!this._visible())return c;let e=this._visibleLists(),r=je(this._config.title,s.defaultReviewTitle);return l`<ha-card>
      ${r?l`<div class="header"><h2 class="title">${r}</h2></div>`:c}
      ${this.renderBanners()}
      ${e?l`${this._renderTabs(e.review.length+e.suggestions.length+(this._unreadEmails()?1:0),e.filtered.length)}
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
    </ha-card>`}_renderTabs(e,r){let n=i=>h(s.tabCount,{label:i==="review"?s.tabReview:s.tabFiltered,count:i==="review"?e:r});return l`<div
      class="tabs"
      role="tablist"
      aria-label=${s.reviewTabs}
      @keydown=${this._onTabKeyDown}
    >
      ${We.map(i=>{let o=this._tab===i;return l`<button
          type="button"
          class="tab"
          role="tab"
          id="tab-${i}"
          data-tab=${i}
          aria-selected=${o?"true":"false"}
          aria-controls="panel-${i}"
          tabindex=${o?"0":"-1"}
          @click=${this._onTabClick}
        >
          ${n(i)}
        </button>`})}
    </div>`}_renderReviewList(e,r){let n=this.snapshot?.settings,i=n?Ss(n.ai_queue,n.ai_queue_seconds):null,o=i?l`<p class="hint queue-hint">${i}</p>`:c,a=this._status,d=l`<div class="action-status" role="status">
      ${a?l`<div class="alert">
            <ha-icon icon=${a.icon} aria-hidden="true"></ha-icon>
            <span class="grow">${a.text}</span>
            <button
              type="button"
              class="icon-btn"
              aria-label=${s.dismissMessage}
              title=${s.dismissMessage}
              @click=${this._dismissStatus}
            >
              <ha-icon icon="mdi:close" aria-hidden="true"></ha-icon>
            </button>
          </div>`:c}
    </div>`,u=this._unreadEmails();return!e.length&&!r.length&&!u?l`${d}${o}<p class="empty">${s.emptyReview}</p>`:l`${d}${o}<div class="items">
      ${u?this._renderUnreadEmails(u):c}
      ${X(r,p=>p.id,(p,g)=>this._renderMergeSuggestion(p,g))}
      ${X(e,p=>p.id,(p,g)=>this._renderReviewItem(p,g))}
    </div>`}_renderUnreadEmails(e){let r=this._busyItems.has(ce)?"true":"false",n=e.newest?E(e.newest,this.locale):"";return l`<article
      class="item"
      tabindex="-1"
      data-item-id=${ce}
      aria-labelledby="unread-emails-title"
      aria-busy=${r}
    >
      <h3 class="subject" id="unread-emails-title">${Ts(e)}</h3>
      ${n?l`<p class="meta">
            ${h(e.count===1?s.receivedOn:s.unreadNewest,{date:n})}
          </p>`:c}
      <p class="hint">${s.unreadHint}</p>
      ${this._renderError(ce)}
      <div class="row-actions">
        <button
          type="button"
          class="btn primary"
          title=${s.unreadRetryHint}
          aria-disabled=${r}
          @click=${this._retryUnread}
        >
          ${s.retry}
        </button>
        <button
          type="button"
          class="btn"
          title=${s.unreadDismissHint}
          aria-disabled=${r}
          @click=${this._dismissUnread}
        >
          ${s.dismiss}
        </button>
      </div>
    </article>`}_renderMergeSuggestion(e,r){let n=this.locale,o=this._busyItems.has(e.id)?"true":"false",a=`suggestion-subject-${r}`,d=it(e.parcel,n),u=Pt(e.reason),p=this.snapshot?.settings,g=p?[...e.candidates].sort(pr(e.parcel,{today:p.today,timeZone:p.time_zone})):e.candidates;return l`<article
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
        ${h(s.suggestionTitle,{parcel:He(e.parcel,n).title})}
      </h3>
      <p class="subject-lines">${this._renderLines(e.parcel)}</p>
      ${u?l`<p class="meta">${h(s.reasonIs,{reason:u})}</p>`:c}
      <p class="hint">${s.suggestionHint}</p>
      <ul class="candidates">
        ${g.map(m=>{let _=it(m,n);return l`<li class="candidate">
            <span class="grow">${this._renderLines(m)}</span>
            <button
              type="button"
              class="btn"
              aria-label=${h(s.mergeSuggestedLabel,{candidate:_,title:d})}
              aria-disabled=${o}
              @click=${()=>this._command(e.id,"suggestion/accept",{suggestion_id:e.id,parcel_id:m.id})}
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
          aria-label=${h(s.keepApartLabel,{title:d})}
          aria-disabled=${o}
          @click=${()=>this._command(e.id,"suggestion/dismiss",{suggestion_id:e.id})}
        >
          ${s.keepApart}
        </button>
      </div>
    </article>`}_renderLines(e){let r=He(e,this.locale),n=nt(e,this.locale);return l`<span class="block"><strong>${r.title}</strong> · ${r.when}</span>
      <span class="meta block">${r.carrier}</span>
      ${n?l`<span class="meta block">${n}</span>`:c}
      ${r.emails?l`<span class="meta block">${r.emails}</span>`:c}
      <span class="meta block items-line">${r.items??r.noItems}</span>`}_renderFilteredList(e){return l`<p class="hint filtered-hint">${s.filteredHint}</p>
      ${e.length?l`${this._renderClearAll()}
            <div class="items">
            ${X(e,r=>r.id,(r,n)=>this._renderFilteredItem(r,n))}
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
      </div>`}_renderHead(e,r,n=c){let i=Ps({subject:e.subject,removed:e.removed===!0});return l`<div class="item-head">
        <span class="sender">${e.sender||e.sender_domain}</span>${n}
      </div>
      <h3 class="subject" id=${r}>${i}</h3>`}_renderError(e){let r=this._itemErrors.get(e);return r?l`<div class="alert error" role="alert">
          <ha-icon icon="mdi:alert-circle-outline" aria-hidden="true"></ha-icon>
          <span class="grow">${r}</span>
        </div>`:c}_renderReviewItem(e,r){let n=this.locale,i=this._busyItems.has(e.id),o=this._editing===e.id,a=`review-subject-${r}`,d=e.received??e.created,u=Vn(e.reason),p=[d?h(s.receivedOn,{date:E(d,n)}):"",e.mailbox_owner?h(s.mailboxOf,{owner:e.mailbox_owner}):"",u?h(s.reasonIs,{reason:u}):""].filter(Boolean),g=e.source==="ai"?l`<span class="badge ai" title=${s.aiSuggestionLabel}>
            ${s.aiBadge}<span class="sr-only">, ${s.aiSuggestionLabel}</span>
          </span>`:c;return l`<article
      class="item"
      tabindex="-1"
      data-item-id=${e.id}
      aria-labelledby=${a}
      aria-busy=${i?"true":"false"}
    >
      ${this._renderHead(e,a,g)}
      ${p.length?l`<p class="meta">${p.join(" \xB7 ")}</p>`:c}
      ${e.authenticated?c:l`<div class="alert warning">
            <ha-icon icon="mdi:shield-alert-outline" aria-hidden="true"></ha-icon>
            <span class="grow">
              <strong class="block">${s.unverifiedSender}</strong>
              ${e.trusted_sender?h(s.trustedSenderNote,{domain:e.sender_domain||e.sender}):s.unverifiedSenderHint}
            </span>
          </div>`}
      ${e.checks?this._renderChecks(e.checks):c}
      ${e.errors.length?this._renderFailedChecks(e.errors):c}
      ${e.notes.length?this._renderNotes(e.notes):c}
      ${o?this._renderEditForm(e,i):this._renderSuggestion(e.suggestion)}
      ${this._renderError(e.id)} ${o?c:this._renderReviewActions(e,i)}
    </article>`}_renderChecks(e){return l`<details class="checks">
      <summary>${s.senderChecks}</summary>
      <dl class="facts">
        ${Es(e).map(([r,n])=>l`<dt>${r}</dt><dd>${n}</dd>`)}
      </dl>
    </details>`}_renderFailedChecks(e){return l`<details class="checks">
      <summary>${s.failedChecks}</summary>
      <ul class="codes">
        ${e.map(r=>{let n=Qn(r);return l`<li><code>${r}</code>${n?`: ${n}`:c}</li>`})}
      </ul>
    </details>`}_renderNotes(e){return l`<details class="checks">
      <summary>${s.aiNotes}</summary>
      <p class="hint">${s.aiNotesHint}</p>
      <ul class="codes">
        ${e.map(r=>{let n=Yn(r);return l`<li><code>${r}</code>${n?`: ${n}`:c}</li>`})}
      </ul>
    </details>`}_renderSuggestion(e){if(!e)return l`<p class="hint section-label">${s.noSuggestion}</p>`;let r=this.locale,n=M(e),i=[[s.fieldKind,et(e.kind)||null],[s.fieldMerchant,e.merchant],[s.fieldCarrier,R({carrier:e.carrier,carrier_name:null})],[s.fieldTrackingNumbers,e.tracking_numbers.join(", ")||null],[s.fieldOrderNumbers,e.order_numbers.join(", ")||null],[s.fieldReference,e.reference],[e.kind==="customer_return"?s.pickup:s.expected,n?F(n.start,n.end,r,Fa):null],[s.timeWindow,le(e.window_start,e.window_end,r)],[s.pickupPoint,e.pickup_point],[s.pickupCode,e.pickup_code],[s.items,e.items.length?l`<ul>
              ${e.items.map(o=>l`<li>${o}</li>`)}
            </ul>`:null]];return l`<p class="section-label">${s.suggestion}</p>
      <dl class="facts">
        ${i.filter(([,o])=>o!==null&&o!=="").map(([o,a])=>l`<dt>${o}</dt><dd>${a}</dd>`)}
      </dl>`}_renderReviewActions(e,r){let n=r?"true":"false",i=e.sender_domain||e.sender;return l`<div class="row-actions">
      ${e.suggestion?l`<button
            type="button"
            class="btn primary"
            aria-disabled=${n}
            @click=${()=>this._accept(e)}
          >
            ${s.accept}
          </button>`:c}
      <button
        type="button"
        class="btn"
        data-edit
        aria-disabled=${n}
        @click=${()=>this._startEdit(e)}
      >
        ${s.edit}
      </button>
      <button
        type="button"
        class="btn"
        aria-disabled=${n}
        @click=${()=>this._command(e.id,"review/dismiss",{review_id:e.id})}
      >
        ${s.dismiss}
      </button>
      ${e.trusted_sender||e.fill?c:l`<button
            type="button"
            class="btn"
            data-trust
            title=${h(s.trustSenderHint,{domain:i})}
            aria-disabled=${n}
            aria-expanded=${e.authenticated?c:this._confirmTrust===e.id?"true":"false"}
            @click=${()=>this._askTrust(e)}
          >
            ${s.trustSender}
          </button>`}
      <button
        type="button"
        class="btn danger"
        title=${h(s.ignoreSenderHint,{domain:i})}
        aria-disabled=${n}
        @click=${()=>this._command(e.id,"review/ignore_sender",{review_id:e.id})}
      >
        ${s.ignoreSender}
      </button>
    </div>
    ${this._confirmTrust===e.id?this._renderTrustConfirm(e,i,r):c}`}_renderTrustConfirm(e,r,n){let i=`trust-question-${e.id}`;return l`<div
      class="confirm"
      role="group"
      aria-labelledby=${i}
      @keydown=${o=>this._onTrustKeyDown(o,e.id)}
    >
      <p id=${i}>${h(s.trustQuestion,{domain:r})}</p>
      <div class="row-actions">
        <button
          type="button"
          class="btn danger primary"
          aria-disabled=${n?"true":"false"}
          @click=${()=>{this._trust(e)}}
        >
          ${h(s.trustConfirm,{domain:r})}
        </button>
        <button type="button" class="btn" data-trust-cancel @click=${()=>this._cancelTrust(e.id)}>
          ${s.cancel}
        </button>
      </div>
    </div>`}_renderEditForm(e,r){let n=this._editForm,i=this._editProblem,o=Object.keys(wt).filter(p=>!Da.has(p)||p===n.kind);o.includes(n.kind)||o.unshift(n.kind);let a=yt();n.carrier&&!Object.hasOwn(he,n.carrier)&&a.unshift({id:n.carrier,name:n.carrier});let d=(p,g,m="text")=>{let _=i?.field===p;return l`<label class="field">
        <span class="field-label">${g}</span>
        <input
          type=${m}
          name=${p}
          autocomplete="off"
          .value=${N(n[p])}
          aria-invalid=${_?"true":"false"}
          aria-describedby=${_?"edit-error":c}
          @input=${this._onEditInput}
        />
      </label>`},u=(p,g,m)=>l`<label class="field">
      <span class="field-label">${g}</span>
      <textarea
        name=${p}
        rows="2"
        autocomplete="off"
        spellcheck="false"
        .value=${N(n[p])}
        aria-describedby=${m}
        @input=${this._onEditInput}
      ></textarea>
    </label>`;return l`<form id="edit-form" class="edit-form" novalidate @submit=${this._submitEdit}>
      <div class="form-grid">
        <label class="field">
          <span class="field-label">${s.fieldKind}</span>
          <select name="kind" data-first @change=${this._onEditInput}>
            ${o.map(p=>l`<option value=${p} ?selected=${p===n.kind}>
                  ${et(p)||p}
                </option>`)}
          </select>
        </label>
        ${d("merchant",s.fieldMerchant)}
        <label class="field">
          <span class="field-label">${s.fieldCarrier}</span>
          <select name="carrier" @change=${this._onEditInput}>
            <option value="" ?selected=${n.carrier===""}>${s.carrierUnknown}</option>
            ${a.map(p=>l`<option value=${p.id} ?selected=${p.id===n.carrier}>
                  ${p.name}
                </option>`)}
          </select>
        </label>
        <div class="field">
          ${u("tracking_numbers",s.fieldTrackingNumbers,"edit-hint-tracking")}
          <p class="hint" id="edit-hint-tracking">${s.hintList}</p>
        </div>
        <div class="field">
          ${u("order_numbers",s.fieldOrderNumbers,"edit-hint-orders")}
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
            .value=${N(n.items)}
            aria-describedby="edit-hint-items"
            @input=${this._onEditInput}
          ></textarea>
          <span class="hint" id="edit-hint-items">${s.hintItems}</span>
        </label>
      </div>
      ${i?l`<div class="alert error" id="edit-error" role="alert">
            <span class="grow">${i.message}</span>
          </div>`:c}
      <div class="row-actions">
        <button type="submit" class="btn primary" aria-disabled=${r?"true":"false"}>
          ${s.acceptWithChanges}
        </button>
        <button type="button" class="btn" @click=${()=>this._cancelEdit(e.id)}>
          ${s.cancel}
        </button>
      </div>
    </form>`}_renderFilteredItem(e,r){let n=`filtered-subject-${r}`,i=e.received??e.created,o=this._busyItems.has(e.id);return l`<article
      class="item"
      tabindex="-1"
      data-item-id=${e.id}
      aria-labelledby=${n}
      aria-busy=${o?"true":"false"}
    >
      ${this._renderHead(e,n)}
      ${i?l`<p class="meta">
            ${h(s.receivedOn,{date:E(i,this.locale)})}
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
    </article>`}_selectTab(e,r){this._tab=e,r&&this.updateComplete.then(()=>this.renderRoot.querySelector(`#tab-${e}`)?.focus())}_onTabClick(e){let r=e.currentTarget.dataset.tab;this._selectTab(r,!1)}_onTabKeyDown(e){let r=We.indexOf(this._tab),n=getComputedStyle(e.currentTarget).direction==="rtl",i;switch(e.key){case"ArrowRight":i=r+(n?-1:1);break;case"ArrowLeft":i=r+(n?1:-1);break;case"Home":i=0;break;case"End":i=We.length-1;break;default:return}e.preventDefault();let o=We[(i+We.length)%We.length];o&&this._selectTab(o,!0)}_focusAfterUpdate(e){this.updateComplete.then(()=>this.renderRoot.querySelector(e)?.focus())}_askClearAll(){this._confirmClearAll=!0,this._focusAfterUpdate("#clear-all-cancel")}_cancelClearAll(){this._confirmClearAll=!1,this._focusAfterUpdate("#clear-all")}_onConfirmKeyDown(e){e.key==="Escape"&&(e.preventDefault(),e.stopPropagation(),this._cancelClearAll())}async _clearAll(){let e=this.hass,r=this._visibleLists()?.filtered.map(n=>n.id)??[];if(!(!e||this._clearingAll||!r.length)){this._clearingAll=!0,this._confirmClearAll=!1,this._hidden=Ur(this._hidden,r),this._focusAfterUpdate("#panel-filtered");try{await K(e,"filtered/clear_all"),this._hidden=Br(this._hidden,r,this.snapshot,n=>this._listed(n))}catch(n){this._hidden=zr(this._hidden,r),this.showActionError(h(s.actionFailed,{message:Y(n)}))}finally{this._clearingAll=!1}}}_focusInItem(e,r){this.updateComplete.then(()=>{let n=this.renderRoot.querySelector(`[data-item-id="${CSS.escape(e)}"]`);(n?.querySelector(r)??n)?.focus()})}_startEdit(e){this._busyItems.has(e.id)||(this._editing=e.id,this._editForm=ar(e.suggestion),this._editProblem=null,this._itemErrors=Wr(this._itemErrors,e.id),this._focusInItem(e.id,"[data-first]"))}_cancelEdit(e){this._editing=null,this._editProblem=null,this._focusInItem(e,"[data-edit]")}_onEditInput(e){let r=e.currentTarget,n=r.name;this._editForm={...this._editForm,[n]:r.value},this._editProblem=null}_submitEdit(e){e.preventDefault();let r=this._editing;if(r===null||this._busyItems.has(r))return;let n=St(this._editForm);if(n){this._editProblem=n,this._focusInItem(r,`[name="${n.field}"]`);return}this._command(r,"review/accept",{review_id:r,overrides:Fn(this._editForm)},{onSuccess:()=>{this._editing===r&&(this._editing=null)}})}_accept(e){this._command(e.id,"review/accept",{review_id:e.id})}_askTrust(e){if(!this._busyItems.has(e.id)){if(e.authenticated){this._trust(e);return}this._confirmTrust=e.id,this._focusInItem(e.id,"[data-trust-cancel]")}}_cancelTrust(e){this._confirmTrust=null,this._focusInItem(e,"[data-trust]")}_onTrustKeyDown(e,r){e.key==="Escape"&&(e.preventDefault(),e.stopPropagation(),this._cancelTrust(r))}async _trust(e){let r=e.sender_domain||e.sender;this._confirmTrust=null,this._status=null,this._focusInItem(e.id,"[data-trust]"),await this._command(e.id,"review/trust_sender",{review_id:e.id},{hide:!1,onSuccess:n=>{let i=n??{};this._status={icon:"mdi:shield-check-outline",text:Rs({domain:i.domain??r,added:i.added??0,rechecking:i.rechecking??0,kept:i.kept??0})}}})}async _retryUnread(){this._status=null,await this._command(ce,"mail/retry_failed",{},{hide:!1,onSuccess:e=>{this._status={icon:"mdi:email-sync-outline",text:As(Yi(e))}}})}async _dismissUnread(){await this._command(ce,"mail/dismiss_failed",{})}_dismissStatus(){this._status=null}async _command(e,r,n,{hide:i=!0,onSuccess:o}={}){let a=this.hass;if(!(!a||this._busyItems.has(e)||this._hidden.has(e))){this._busyItems=new Set([...this._busyItems,e]),this._itemErrors=Wr(this._itemErrors,e),i&&(this._hidden=Ur(this._hidden,[e]));try{let d=await K(a,r,n);i&&(this._hidden=Br(this._hidden,[e],this.snapshot,u=>this._listed(u))),o?.(d)}catch(d){this._hidden=zr(this._hidden,[e]);let u=h(s.actionFailed,{message:Y(d)});this._listed(e)?this._itemErrors=new Map([...this._itemErrors,[e,u]]):this.showActionError(u)}finally{let d=new Set(this._busyItems);d.delete(e),this._busyItems=d}}}};W("parcels-review-card",qr);Me("parcels-review-card",s.reviewCardName,s.reviewCardDescription);
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
