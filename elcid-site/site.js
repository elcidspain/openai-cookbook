// Language comes only from the URL path (/, /en, /de, /fr, /nl, /ru, /it).
// No browser-language or stored-preference switching; each page is static HTML.
const $=(s,c=document)=>c.querySelector(s),$$=(s,c=document)=>[...c.querySelectorAll(s)];
try{localStorage.removeItem('elcid-language')}catch{}
const languageMenu=$('#languageMenu');if(languageMenu){$$('.lang-menu a',languageMenu).forEach(a=>a.addEventListener('click',()=>{if(location.hash&&!a.hasAttribute('aria-current'))a.href=a.getAttribute('href')+location.hash}));document.addEventListener('click',e=>{if(languageMenu.open&&!languageMenu.contains(e.target))languageMenu.open=false});addEventListener('keydown',e=>{if(e.key==='Escape'&&languageMenu.open){languageMenu.open=false;$('summary',languageMenu).focus()}})}
const prefersMotion=matchMedia('(prefers-reduced-motion:no-preference)');const header=$('#header');addEventListener('scroll',()=>{header.classList.toggle('solid',scrollY>60);const bg=$('.hero-bg');if(bg&&prefersMotion.matches)bg.style.transform=`scale(1.04) translateY(${Math.min(scrollY*.08,45)}px)`},{passive:true});
const menu=$('#menuButton'),panel=$('#mobilePanel');menu.addEventListener('click',()=>{const open=panel.classList.toggle('open');menu.setAttribute('aria-expanded',String(open))});$$('#mobilePanel a,#mobilePanel button').forEach(el=>el.addEventListener('click',()=>{panel.classList.remove('open');menu.setAttribute('aria-expanded','false')}));
const drawer=$('#bookingDrawer'),backdrop=$('#bookingBackdrop'),close=$('#closeBooking');function openBooking(){drawer.classList.add('open');drawer.setAttribute('aria-hidden','false');backdrop.hidden=false;document.body.classList.add('drawer-open');setTimeout(()=>close.focus(),120)}function closeBooking(){drawer.classList.remove('open');drawer.setAttribute('aria-hidden','true');backdrop.hidden=true;document.body.classList.remove('drawer-open')}$$('[data-open-booking]').forEach(el=>el.addEventListener('click',e=>{e.preventDefault();openBooking()}));close.addEventListener('click',closeBooking);backdrop.addEventListener('click',closeBooking);addEventListener('keydown',e=>{if(e.key==='Escape')closeBooking()});
const nudge=$('#bookingNudge');const bookingFooter=$('footer');let bookingFooterVisible=false;
if(bookingFooter){new IntersectionObserver(entries=>{bookingFooterVisible=entries.some(e=>e.isIntersecting);if(bookingFooterVisible)nudge.hidden=true}).observe(bookingFooter)}
setTimeout(()=>{try{if(!bookingFooterVisible&&!document.body.classList.contains('drawer-open')&&!$('.elcid-consent:not([hidden])')&&!sessionStorage.getItem('elcid-nudge')){nudge.hidden=false;sessionStorage.setItem('elcid-nudge','1')}}catch{}},7000);
$('button:not(.nudge-action)',nudge).addEventListener('click',()=>nudge.hidden=true);$('.nudge-action',nudge).addEventListener('click',()=>nudge.hidden=true);
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


// Date-aware guest quotes from the existing read-only Beds24 API.
// Checkout stays on Beds24; a quote never holds a room or collects payment.
(() => {
  const drawer = document.getElementById('bookingDrawer');
  const direct = drawer?.querySelector('.direct-option');
  if (!drawer || !direct || drawer.querySelector('.elcid-live-search')) return;
  const locale = (document.documentElement.lang || 'es').split('-')[0];
  const phrases = {
    es: ['Consultar disponibilidad en directo','Entrada','Salida','Adultos','Niños','Buscar habitaciones y precios','Consultando Beds24…','Sin oferta online para estas fechas. Prueba otras fechas o consulta en Beds24.','La consulta no está disponible ahora. Puedes continuar directamente en Beds24.','Reservar esta opción','Total de la estancia','Precio final y condiciones en el checkout de Beds24. No se ha realizado una reserva.','La salida debe ser posterior a la entrada.'],
    en: ['Check live availability','Check-in','Check-out','Adults','Children','Find rooms and prices','Checking Beds24…','No online offer for these dates. Try another date or check Beds24.','Live quotes are unavailable right now. You can continue directly on Beds24.','Book this option','Stay total','Final price and conditions are confirmed in Beds24 checkout. No reservation has been made.','Check-out must be after check-in.'],
    de: ['Live-Verfügbarkeit prüfen','Anreise','Abreise','Erwachsene','Kinder','Zimmer und Preise suchen','Beds24 wird geprüft…','Kein Online-Angebot für diese Daten. Bitte andere Daten oder Beds24 prüfen.','Live-Preise sind derzeit nicht verfügbar. Direktbuchung über Beds24 bleibt möglich.','Diese Option buchen','Gesamtpreis','Endpreis und Bedingungen werden bei Beds24 bestätigt. Es wurde nicht gebucht.','Die Abreise muss nach der Anreise liegen.'],
    fr: ['Consulter les disponibilités','Arrivée','Départ','Adultes','Enfants','Voir les chambres et tarifs','Consultation de Beds24…','Aucune offre en ligne pour ces dates. Essayez d’autres dates ou Beds24.','Les tarifs en direct sont indisponibles. Vous pouvez continuer sur Beds24.','Réserver cette option','Total du séjour','Prix final et conditions confirmés sur Beds24. Aucune réservation effectuée.','Le départ doit être après l’arrivée.'],
    nl: ['Live beschikbaarheid bekijken','Aankomst','Vertrek','Volwassenen','Kinderen','Kamers en prijzen zoeken','Beds24 controleren…','Geen online aanbod voor deze data. Kies andere data of controleer Beds24.','Live prijzen zijn tijdelijk niet beschikbaar. Ga rechtstreeks naar Beds24.','Deze optie boeken','Totaal verblijf','Definitieve prijs en voorwaarden staan bij Beds24. Er is niets geboekt.','Vertrek moet na aankomst liggen.'],
    ru: ['Проверить наличие и цены','Заезд','Выезд','Взрослые','Дети','Найти номера и цены','Проверяем Beds24…','Для этих дат онлайн-предложений нет. Попробуйте другие даты или откройте Beds24.','Цены временно недоступны. Можно перейти непосредственно в Beds24.','Забронировать вариант','Итого за проживание','Окончательные цена и условия — в Beds24. Бронирование ещё не создано.','Дата выезда должна быть позже заезда.'],
    it: ['Verifica disponibilità','Arrivo','Partenza','Adulti','Bambini','Cerca camere e prezzi','Verifica Beds24…','Nessuna offerta online per queste date. Prova altre date o Beds24.','I prezzi in diretta non sono disponibili. Prosegui su Beds24.','Prenota questa opzione','Totale soggiorno','Prezzo finale e condizioni nel checkout Beds24. Nessuna prenotazione effettuata.','La partenza deve essere dopo l’arrivo.']
  };
  const t = phrases[locale] || phrases.en;
  const form = document.createElement('form');
  form.className = 'elcid-live-search';
  form.setAttribute('aria-label', t[0]);
  const heading = document.createElement('h3');
  heading.textContent = t[0];
  form.appendChild(heading);
  function field(text, type, min, max) {
    const label = document.createElement('label');
    label.className = 'elcid-live-field';
    const caption = document.createElement('span');
    caption.textContent = text;
    const input = document.createElement('input');
    input.type = type;
    input.required = true;
    if (min !== undefined) input.min = String(min);
    if (max !== undefined) input.max = String(max);
    label.append(caption, input);
    form.appendChild(label);
    return input;
  }
  const today = new Date();
  const isoToday = [today.getFullYear(), String(today.getMonth()+1).padStart(2,'0'), String(today.getDate()).padStart(2,'0')].join('-');
  const addDay = value => { const date = new Date(value+'T00:00:00Z'); date.setUTCDate(date.getUTCDate()+1); return date.toISOString().slice(0,10); };
  const arrival = field(t[1], 'date', isoToday);
  const departure = field(t[2], 'date', addDay(isoToday));
  arrival.addEventListener('change', () => {
    if (!arrival.value) return;
    departure.min = addDay(arrival.value);
    if (departure.value && departure.value < departure.min) departure.value = '';
  });
  const adults = field(t[3], 'number', 1, 20);
  adults.value = '2';
  const children = field(t[4], 'number', 0, 20);
  children.value = '0';
  const submit = document.createElement('button');
  submit.type = 'submit';
  submit.className = 'button green elcid-live-submit';
  submit.textContent = t[5];
  const result = document.createElement('div');
  result.className = 'elcid-live-result';
  result.setAttribute('role', 'status');
  result.setAttribute('aria-live', 'polite');
  form.append(submit, result);
  drawer.insertBefore(form, direct);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    if (departure.value <= arrival.value) {
      result.replaceChildren(document.createTextNode(t[12]));
      return;
    }
    const params = new URLSearchParams({
      checkIn: arrival.value,
      checkOut: departure.value,
      adults: adults.value,
      children: children.value
    });
    const requestedIn = arrival.value, requestedOut = departure.value;
    submit.disabled = true;
    result.replaceChildren(document.createTextNode(t[6]));
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch('/api/availability?' + params, {cache:'no-store', signal:controller.signal});
      if (!response.ok) throw new Error('Quote HTTP ' + response.status);
      const quote = await response.json();
      if (quote.checkIn !== requestedIn || quote.checkOut !== requestedOut || !Array.isArray(quote.inventory)) throw new Error('Invalid quote');
      const choices = quote.inventory.filter(room =>
        room.bookable === true && room.availableUnits > 0 && Number.isFinite(room.stayTotal) &&
        typeof room.checkoutUrl === 'string'
      );
      result.replaceChildren();
      if (!choices.length) {
        result.textContent = t[7];
        return;
      }
      for (const room of choices) {
        let checkout;
        try { checkout = new URL(room.checkoutUrl); } catch { continue; }
        if (checkout.protocol !== 'https:' || checkout.hostname !== 'beds24.com') continue;
        const article = document.createElement('div');
        article.className = 'elcid-quote-row';
        const label = document.createElement('strong');
        label.textContent = room.name;
        const price = document.createElement('span');
        const currency = /^[A-Z]{3}$/.test(room.currency || '') ? room.currency : 'EUR';
        price.textContent = t[10] + ': ' + new Intl.NumberFormat(locale, {style:'currency', currency}).format(room.stayTotal);
        const link = document.createElement('a');
        link.className = 'elcid-quote-link';
        link.textContent = t[9] + ' ↗';
        link.href = checkout.href;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        article.append(label, price, link);
        result.appendChild(article);
      }
      if (!result.childElementCount) result.textContent = t[7];
      else {
        const notice = document.createElement('small');
        notice.textContent = t[11];
        result.appendChild(notice);
      }
    } catch {
      result.textContent = t[8];
    } finally {
      clearTimeout(timeout);
      submit.disabled = false;
    }
  });
})();


// EL CID public storefront only. No vendor starts before specific consent.
(() => {
  'use strict';
  const GA = ''; // Build-time configuration: EL CID's verified stream only.
  const HOSTS = new Set(['elcidspain.com','www.elcidspain.com']);
  const PUBLIC = new Set(['/','/en','/de','/fr','/nl','/ru','/it']);
  const page = location.pathname.replace(/\/+$/,'') || '/';
  if (!HOSTS.has(location.hostname) || !PUBLIC.has(page) || !GA) return;
  const KEY = 'elcid-analytics-consent-v1', MAX_AGE = 180 * 86400000;
  const allowedParams = new Set(['utm_source','utm_medium','utm_campaign','utm_content','utm_term']);
  const params = new URLSearchParams(location.search);
  const knownAnchor = /^#(?:top|main|intro|stay|restaurant|place|events|contact|aumara|tennis|pool|availability)$/;
  if ([...params.keys()].some(k=>!allowedParams.has(k)) || (location.hash && !knownAnchor.test(location.hash))) return;
  const campaign = new URLSearchParams();
  for (const k of allowedParams) {
    const v = params.get(k);
    if (v && /^[a-z0-9_-]{1,80}$/i.test(v)) campaign.set(k,v);
  }
  const pageLocation = location.origin + page + (campaign.size ? '?' + campaign : '');
  let referrer = '';
  try { if (document.referrer) referrer = new URL(document.referrer).origin + '/'; } catch {}
  const denyAds = {ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',personalization_storage:'denied'};
  let accepted = false, started = false;
  function preference() {
    try {
      const c = JSON.parse(localStorage.getItem(KEY) || 'null');
      return c && typeof c.at==='number' && c.at<=Date.now() && Date.now()-c.at<MAX_AGE && typeof c.analytics==='boolean' ? c : null;
    } catch { return null; }
  }
  function clearCookies() {
    for (const pair of document.cookie.split(';')) {
      const name = pair.split('=')[0].trim();
      if (!/^_ga(?:_[A-Z0-9]+)?$/.test(name)) continue;
      for (const domain of ['', '; Domain='+location.hostname,'; Domain=.elcidspain.com'])
        document.cookie = name+'=; Max-Age=0; Path=/; Secure; SameSite=Lax'+domain;
    }
  }
  function send(name) {
    if (!accepted || !['booking_open','availability_search','booking_checkout_click','restaurant_contact_click','aumara_referral_click'].includes(name)) return;
    if (typeof window.gtag==='function') window.gtag('event',name,{send_to:GA,page_location:pageLocation,page_referrer:referrer});
  }
  function enable() {
    accepted = true;
    if (started) return;
    started = true;
    window['ga-disable-'+GA] = false;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function(){ window.dataLayer.push(arguments); };
    window.gtag('consent','default',{...denyAds,analytics_storage:'denied',functionality_storage:'granted',security_storage:'granted'});
    window.gtag('consent','update',{...denyAds,analytics_storage:'granted'});
    window.gtag('set','ads_data_redaction',true);
    window.gtag('set','url_passthrough',false);
    window.gtag('js',new Date());
    window.gtag('config',GA,{send_page_view:false,allow_google_signals:false,allow_ad_personalization_signals:false,cookie_expires:15552000,cookie_update:false,page_location:pageLocation,page_referrer:referrer});
    const tag = document.createElement('script');
    tag.async = true;tag.src = 'https://www.googletagmanager.com/gtag/js?id='+GA;
    document.head.append(tag);
    window.gtag('event','page_view',{send_to:GA,page_location:pageLocation,page_referrer:referrer});
  }
  function disable() {
    accepted = false;window['ga-disable-'+GA] = true;clearCookies();
    // Reload only if a vendor was running. A revoked tag must not stay active.
    if(started){window.gtag=function(){};location.reload();}
  }
  const copy = {
    es:['Preferencias de cookies','Usamos almacenamiento esencial para el sitio. Google Analytics mide las visitas y los clics de reserva solo con tu consentimiento. No se activa publicidad.','Aceptar analítica','Rechazar','Configurar cookies','Política de cookies'],
    en:['Cookie preferences','Essential storage keeps the site working. Google Analytics measures public visits and booking clicks only with your consent. Advertising is disabled.','Accept analytics','Reject','Cookie settings','Cookie policy'],
    ru:['Настройки cookies','Обязательное хранение обеспечивает работу сайта. Google Analytics измеряет посещения и переходы к бронированию только с вашего согласия. Реклама отключена.','Принять аналитику','Отклонить','Настроить cookies','Политика cookies'],
    de:['Cookie-Einstellungen','Google Analytics misst Besuche und Buchungsklicks nur mit Ihrer Einwilligung. Werbung ist deaktiviert.','Analyse akzeptieren','Ablehnen','Cookie-Einstellungen','Cookie-Richtlinie'],
    fr:['Préférences de cookies','Google Analytics mesure les visites et les clics de réservation uniquement avec votre accord. La publicité est désactivée.','Accepter les statistiques','Refuser','Paramètres des cookies','Politique de cookies'],
    nl:['Cookievoorkeuren','Google Analytics meet bezoeken en boekingsklikken alleen met uw toestemming. Advertenties staan uit.','Analytics accepteren','Weigeren','Cookie-instellingen','Cookiebeleid'],
    it:['Preferenze cookie','Google Analytics misura visite e clic di prenotazione solo con il tuo consenso. La pubblicità è disattivata.','Accetta analisi','Rifiuta','Impostazioni cookie','Informativa cookie']
  };
  const t = copy[(document.documentElement.lang || 'es').split('-')[0]] || copy.en;
  const panel = document.createElement('section'); panel.className='elcid-consent';panel.setAttribute('aria-label',t[0]);
  const title = document.createElement('strong');title.textContent=t[0];
  const msg = document.createElement('p');msg.textContent=t[1];
  const controls = document.createElement('div');controls.className='elcid-consent-actions';
  const button = text=>{const el=document.createElement('button');el.type='button';el.textContent=text;return el;};
  const yes=button(t[2]),no=button(t[3]),settings=button(t[4]),configure=button(t[4]);
  const policy=document.createElement('a');policy.href='/cookie-policy';policy.textContent=t[5];
  const footer=document.querySelector('footer nav') || document.body;
  settings.className='elcid-consent-settings';footer.append(settings);
  function openSettings() {panel.hidden=false;title.tabIndex=-1;title.focus();}
  settings.addEventListener('click',openSettings);
  configure.addEventListener('click',()=>{configure.hidden=true;msg.textContent=t[1];yes.focus();});
  function choose(analytics) {
    try {localStorage.setItem(KEY,JSON.stringify({analytics,at:Date.now()}));}
    catch {if(analytics)return;}
    panel.hidden=true;configure.hidden=false;
    if(analytics)enable();else disable();
  }
  yes.addEventListener('click',()=>choose(true));no.addEventListener('click',()=>choose(false));
  controls.append(yes,no,configure,policy);panel.append(title,msg,controls);document.body.append(panel);
  const stored=preference();panel.hidden=!!stored;
  if(stored?.analytics)enable();else disable();
  window.addEventListener('storage',e=>{if(e.key===KEY||e.key===null){if(preference()?.analytics)enable();else disable();}});
  document.addEventListener('click',e=>{
    if(e.target?.closest?.('[data-open-booking]'))send('booking_open');
    const a=e.target?.closest?.('a[href]');if(!a)return;
    let u;try{u=new URL(a.href,location.href);}catch{return;}
    if(u.protocol!=='https:')return;
    if(u.hostname==='beds24.com'||u.hostname==='www.beds24.com'||u.hostname==='www.booking.com')send('booking_checkout_click');
    else if(['aumara.me','www.aumara.me'].includes(u.hostname))send('aumara_referral_click');
    else if(u.hostname==='wa.me'&&a.closest('#restaurant'))send('restaurant_contact_click');
  },true);
  document.addEventListener('submit',e=>{if(e.target?.classList?.contains('elcid-live-search'))send('availability_search');},true);
})();
