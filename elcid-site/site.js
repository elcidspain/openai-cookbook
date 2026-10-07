// Language comes only from the URL path (/, /en, /de, /fr, /nl, /ru, /it).
// No browser-language or stored-preference switching; each page is static HTML.
const $=(s,c=document)=>c.querySelector(s),$$=(s,c=document)=>[...c.querySelectorAll(s)];
try{localStorage.removeItem('elcid-language')}catch{}
const languageMenu=$('#languageMenu');if(languageMenu){$$('.lang-menu a',languageMenu).forEach(a=>a.addEventListener('click',()=>{if(location.hash&&!a.hasAttribute('aria-current'))a.href=a.getAttribute('href')+location.hash}));document.addEventListener('click',e=>{if(languageMenu.open&&!languageMenu.contains(e.target))languageMenu.open=false});addEventListener('keydown',e=>{if(e.key==='Escape'&&languageMenu.open){languageMenu.open=false;$('summary',languageMenu).focus()}})}
const prefersMotion=matchMedia('(prefers-reduced-motion:no-preference)');const header=$('#header');addEventListener('scroll',()=>{header.classList.toggle('solid',scrollY>60);const bg=$('.hero-bg');if(bg&&prefersMotion.matches)bg.style.transform=`scale(1.04) translateY(${Math.min(scrollY*.08,45)}px)`},{passive:true});
const menu=$('#menuButton'),panel=$('#mobilePanel');menu.addEventListener('click',()=>{const open=panel.classList.toggle('open');menu.setAttribute('aria-expanded',String(open))});$$('#mobilePanel a,#mobilePanel button').forEach(el=>el.addEventListener('click',()=>{panel.classList.remove('open');menu.setAttribute('aria-expanded','false')}));
const drawer=$('#bookingDrawer'),backdrop=$('#bookingBackdrop'),close=$('#closeBooking');function openBooking(){drawer.classList.add('open');drawer.setAttribute('aria-hidden','false');backdrop.hidden=false;document.body.classList.add('drawer-open');setTimeout(()=>close.focus(),120)}function closeBooking(){drawer.classList.remove('open');drawer.setAttribute('aria-hidden','true');backdrop.hidden=true;document.body.classList.remove('drawer-open')}$$('[data-open-booking]').forEach(el=>el.addEventListener('click',e=>{e.preventDefault();openBooking()}));close.addEventListener('click',closeBooking);backdrop.addEventListener('click',closeBooking);addEventListener('keydown',e=>{if(e.key==='Escape')closeBooking()});
const nudge=$('#bookingNudge');setTimeout(()=>{if(!sessionStorage.getItem('elcid-nudge')){nudge.hidden=false;sessionStorage.setItem('elcid-nudge','1')}},7000);$('button:not(.nudge-action)',nudge).addEventListener('click',()=>nudge.hidden=true);$('.nudge-action',nudge).addEventListener('click',()=>nudge.hidden=true);
document.documentElement.classList.add('reveal-ready');const observer=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('visible');observer.unobserve(e.target)}}),{threshold:.12});$$('[data-reveal]').forEach(el=>observer.observe(el));

// WebMCP: read-only public tools for agent-capable browsers.
(async()=>{
  const modelContext=document.modelContext||navigator.modelContext;
  if(!modelContext?.registerTool)return;
  const register=async(tool)=>{try{await modelContext.registerTool(tool)}catch{}};
  await register({
    name:'elcid_guest_guide',
    title:'EL CID Country Club guest guide',
    description:'Read the public EL CID country-club stay, restaurant, outdoor, contact, policy and booking guidance. Read-only.',
    inputSchema:{type:'object',properties:{},additionalProperties:false},
    annotations:{readOnlyHint:true,untrustedContentHint:false,consequentialHint:false},
    execute:async()=>await fetch('/llms.txt',{cache:'no-store'}).then(r=>r.text())
  });
  await register({
    name:'elcid_booking_options',
    title:'EL CID public booking options',
    description:'Return the public Booking.com and contact routes shown by EL CID. This does not create a reservation. Read-only.',
    inputSchema:{type:'object',properties:{},additionalProperties:false},
    annotations:{readOnlyHint:true,untrustedContentHint:false,consequentialHint:false},
    execute:async()=>JSON.stringify({
      property:'EL CID Country Club',
      location:'Benidoleig, Alicante, Spain',
      booking:'https://www.booking.com/hotel/es/el-cid-country-club.html',
      whatsapp:'https://wa.me/34622914323',
      website:'https://www.elcidspain.com/'
    })
  });
})();
