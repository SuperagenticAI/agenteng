#!/usr/bin/env node
// Read public literal data using the TypeScript AST; never execute website code.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';

const root = path.resolve(process.argv[2] ?? '../agent-engineering-summit');
const output = path.resolve(process.argv[3] ?? 'src/agenteng/data/catalogue.json');
const require = createRequire(path.join(root, 'package.json'));
const ts = require('typescript');
const definitions = new Map();
const values = new Map();
const trees = new Map();
const hash = crypto.createHash('sha256');
function read(file) {
  const text = fs.readFileSync(path.join(root, file), 'utf8');
  hash.update(file).update(text);
  const tree = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true,
    file.endsWith('tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  trees.set(file, tree);
  for (const statement of tree.statements) {
    if (ts.isVariableStatement(statement)) for (const d of statement.declarationList.declarations) {
      if (ts.isIdentifier(d.name) && d.initializer) definitions.set(d.name.text, d.initializer);
    }
  }
  return text;
}
function constant(name) {
  if (!values.has(name)) {
    if (!definitions.has(name)) throw new Error(`Unknown public constant: ${name}`);
    values.set(name, evaluate(definitions.get(name)));
  }
  return values.get(name);
}
function evaluate(n) {
  if (ts.isAsExpression(n) || ts.isParenthesizedExpression(n)) return evaluate(n.expression);
  if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) return n.text;
  if (ts.isNumericLiteral(n)) return Number(n.text);
  if (n.kind === ts.SyntaxKind.TrueKeyword) return true;
  if (n.kind === ts.SyntaxKind.FalseKeyword) return false;
  if (ts.isIdentifier(n)) return constant(n.text);
  if (ts.isArrayLiteralExpression(n)) return n.elements.map(evaluate);
  if (ts.isObjectLiteralExpression(n)) return Object.fromEntries(n.properties.map(p => {
    if (!ts.isPropertyAssignment(p)) throw new Error('Non-literal public object');
    return [p.name.text, evaluate(p.initializer)];
  }));
  if (ts.isPropertyAccessExpression(n)) return evaluate(n.expression)[n.name.text];
  if (ts.isTemplateExpression(n)) return n.head.text + n.templateSpans.map(
    s => String(evaluate(s.expression)) + s.literal.text).join('');
  if (ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression) &&
      n.expression.name.text === 'join') {
    const array = evaluate(n.expression.expression);
    if (!Array.isArray(array)) throw new Error('join requires literal array');
    return array.join(n.arguments.length ? evaluate(n.arguments[0]) : ',');
  }
  throw new Error(`Unsupported expression in public export: ${ts.SyntaxKind[n.kind]}`);
}
// JSX prose (manifesto, chair card) is read as text nodes only; markup is dropped.
function walk(node, visit) { visit(node); ts.forEachChild(node, child => walk(child, visit)); }
function tagName(n) {
  const open = ts.isJsxElement(n) ? n.openingElement : ts.isJsxSelfClosingElement(n) ? n : null;
  return open ? open.tagName.getText() : null;
}
function jsxText(n) {
  if (ts.isJsxText(n)) return n.text;
  if (ts.isJsxExpression(n)) return n.expression && (ts.isStringLiteral(n.expression) ||
    ts.isNoSubstitutionTemplateLiteral(n.expression)) ? n.expression.text : '';
  if (ts.isJsxElement(n) || ts.isJsxFragment(n)) return n.children.map(jsxText).join('');
  return '';
}
const prose = text => text.replace(/\s+/g, ' ').replace(/\s+([.,;:])/g, '$1').trim();
function jsxTexts(file, tag) {
  const out = [];
  walk(trees.get(file), n => { if (tagName(n) === tag) out.push(prose(jsxText(n))); });
  return out;
}
function jsxAttribute(file, tag, key, keyValue, wanted) {
  let found = null;
  walk(trees.get(file), n => {
    const open = ts.isJsxElement(n) ? n.openingElement : ts.isJsxSelfClosingElement(n) ? n : null;
    if (!open || open.tagName.getText() !== tag) return;
    const attrs = Object.fromEntries(open.attributes.properties.filter(ts.isJsxAttribute)
      .filter(a => a.initializer && ts.isStringLiteral(a.initializer))
      .map(a => [a.name.getText(), a.initializer.text]));
    if (attrs[key] === keyValue && attrs[wanted]) found = attrs[wanted];
  });
  if (!found) throw new Error(`Missing ${tag} ${key}=${keyValue} in ${file}`);
  return found;
}
// Evaluate only the named literal fields of an array of objects (icons are components).
function pickFields(name, keys) {
  return constant.definitionsOnly(name).elements.map(element => Object.fromEntries(keys.map(key => {
    const prop = element.properties.find(p => ts.isPropertyAssignment(p) && p.name.text === key);
    if (!prop) throw new Error(`Missing ${key} in ${name}`);
    return [key, evaluate(prop.initializer)];
  })));
}
constant.definitionsOnly = name => {
  if (!definitions.has(name)) throw new Error(`Unknown public constant: ${name}`);
  return definitions.get(name);
};
function nestedConstant(file, name) {
  let found = null;
  walk(trees.get(file), n => {
    if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === name) found = n.initializer;
  });
  if (!found) throw new Error(`Missing ${name} in ${file}`);
  return evaluate(found);
}
function only(rows, test, label) {
  const hits = rows.filter(test);
  if (hits.length !== 1) throw new Error(`Expected one ${label}, found ${hits.length}`);
  return hits[0];
}
read('src/data/agenda.ts');
read('src/data/speakers.ts');
read('src/data/tickets.ts');
read('src/data/london-events.ts');
read('src/data/contact.ts');
read('src/data/venue.ts');
read('src/data/disciplines.ts');
const sfText = read('src/pages/SanFrancisco.tsx');
const sponsorText = read('src/components/SponsorStrip.tsx');
const tracksText = read('src/components/ProgramTracksSection.tsx');
const sponsorsPage = read('src/pages/Sponsors.tsx');
const roster = constant('roster');
values.set('speakers', [...roster].sort((a,b) => (b.listedOn ?? b.announcedOn).localeCompare(a.listedOn ?? a.announcedOn)));
values.set('whoIsSpeakingAnswer', 'The lineup: ' + roster.map(
  s => `${s.name}, ${s.role} at ${s.company}`).join('; ') + '. See the published speakers page.');
read('src/components/FAQSection.tsx');
const site = 'https://agentengineering.world';
const sources = [];
function source(id, url, text, event_id, kind = 'document') {
  sources.push({id, url, text, event_id, kind}); return id;
}
const london = 'agenteng-london-2026';
const londonSource = source(london, site+'/london-2026', 'AgentEng London 2026. 16 October 2026. Everyman Canary Wharf, Crossrail Place, London E14 5AR.', london, 'event');
const ticketSource = source('london-ticket-terms', site+'/london-2026',
  JSON.stringify({offers: constant('tickets'), registration:constant('LUMA_EVENT_URL'), approval:constant('approvalGateBody')}), london, 'tickets');
const nextDay = iso => new Date(Date.parse(iso+'T00:00:00Z') + 86400000).toISOString().slice(0,10);
const offers = Object.values(constant('tickets')).map(v => ({name:v.name,
  amount:v.price,currency:'GBP',valid_from:(v.fromIso ?? v.validFromIso)+'T00:00:00+01:00',
  valid_until:v.untilIso ? nextDay(v.untilIso)+'T00:00:00+01:00' : null,sold_out:!!v.soldOut}));
const participationText=fs.readFileSync(path.join(root,'public/llms.txt'),'utf8');
hash.update('public/llms.txt').update(participationText);
const invitationPolicy='Speaker applications: the programme is invited; no public CFP for this edition';
if (!participationText.includes(invitationPolicy)) throw new Error('London participation policy changed; review catalogue export');
const policySource=source('london-participation-policy',site+'/llms.txt',
  'AgentEng London 2026. '+invitationPolicy+'.',london,'participation');
// Times and venue come from the website's public calendar. Assert the literals
// used below so a calendar edit cannot silently leave a stale event envelope.
const londonICS=fs.readFileSync(path.join(root,'public/agenteng-london-2026.ics'),'utf8');
hash.update('public/agenteng-london-2026.ics').update(londonICS);
for (const required of ['DTSTART:20261016T070000Z','DTEND:20261016T153000Z',
  'Everyman Canary Wharf', 'Crossrail Place', 'London E14 5AR']) {
  if (!londonICS.includes(required)) throw new Error('London calendar drift: '+required);
}
const calendarSource=source('london-calendar',site+'/agenteng-london-2026.ics',londonICS,london,'calendar');
const venueTour = constant('VENUE_TOUR_URL');
const events = [{id:london,title:'AgentEng London 2026',city:'London',timezone:'Europe/London',
  date:'2026-10-16',venue:'Everyman Canary Wharf, Crossrail Place, London E14 5AR',
  venue_tour_url:venueTour,track:'single',
  start:'2026-10-16T08:00:00+01:00',end:'2026-10-16T16:30:00+01:00',
  registration_url:constant('LUMA_EVENT_URL'),offers,speaker_submission_status:'invited_only',source_ids:[londonSource,ticketSource,calendarSource,policySource]}];
const speakerDisciplines = constant('SPEAKER_DISCIPLINES');
const speakers = roster.map(s => {
  const abstract = s.talk ? [].concat(s.talk.abstract).join('\n\n') : null;
  const projects = (s.projects || []).map(p => ({name:p.name,url:p.url,blurb:p.blurb || ''}));
  const links = s.links ? Object.fromEntries(Object.entries(s.links).filter(([,v]) => v)) : null;
  const location = s.location ? {city:s.location.city || null,country:s.location.country} : null;
  const disciplines = speakerDisciplines[s.slug] || [];
  const id = source('speaker-'+s.slug,site+'/london-2026/speakers#'+s.slug,
    `${s.name}, ${s.role} at ${s.company}. ${s.talk?.title ?? 'Talk not announced'}. ${abstract ?? ''}`,london,'speaker');
  return {id:s.slug,name:s.name,role:s.role,company:s.company,
    company_url:s.companyUrl || null,note:s.note || null,location,links,projects,
    announced_on:s.announcedOn || null,disciplines,event_ids:[london],
    talk_title:s.talk?.title ?? null,abstract,source_ids:[id]};
});
const topics = text => [...new Set(['memory','evaluation','harness','context','security','voice','coding','mcp','acp','inference']
  .filter(t => text.toLowerCase().includes(t === 'evaluation' ? 'eval' : t)))];
const agendaIds = new Set();
const sessions = constant('agenda').map(s => {
  if (typeof s.id !== 'string' || !s.id.startsWith(london+'-') || agendaIds.has(s.id)) {
    throw new Error('Every agenda slot requires a unique, stable public id scoped to the London event');
  }
  agendaIds.add(s.id);
  const speaker = speakers.find(p => p.id === s.speakerSlug);
  const id = source(`london-session-${s.id.slice(london.length+1)}`,site+'/london-2026/agenda',
    `${s.time} ${s.title}. ${speaker?.name ?? ''}. ${speaker?.abstract ?? s.note ?? ''}`,london,'session');
  return {id:s.id,event_id:london,title:s.title,kind:s.kind,
    start:`2026-10-16T${s.time}:00+01:00`,end:s.end ? `2026-10-16T${s.end}:00+01:00` : null,
    speaker_id:s.speakerSlug ?? null,topics:topics(s.title+' '+(speaker?.abstract ?? '')),source_ids:[id]};
});
const months = Object.fromEntries(['January','February','March','April','May','June','July','August','September','October','November','December'].map((m,i)=>[m,String(i+1).padStart(2,'0')]));
const slug = text => text.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
for (const e of constant('londonPastEvents')) {
  const [month,year] = e.date.split(' '); const id = 'london-'+slug(e.title);
  const ref = source(id,e.page ?? site+'/london',`${e.title}. ${e.date}. ${e.venue}.`,id,'event');
  events.push({id,title:e.title,city:'London',timezone:'Europe/London',date:`${year}-${months[month]}`,
    date_precision:'month',venue:e.venue,registration_url:e.luma ?? e.meetup ?? null,
    recording_url:e.videoId ? `https://www.youtube.com/watch?v=${e.videoId}` : null,source_ids:[ref]});
}
// Inline SF metadata is verified against the public page; fail on source drift.
for (const e of [
  {id:'sf-code-engineering-2026',title:'Code Engineering: From Coding Agents to Software Factories',date:'2026-10-27',marker:'27 October 2026',registration:'https://luma.com/cico2dxy',roster:'upcomingSpeakers',start:'2026-10-27T18:00:00-07:00'},
  {id:'sf-harness-engineering-2026',title:'Harness Engineering: State of the Art in Agent Harnesses',date:'2026-07-03',marker:'3 July 2026',registration:'https://luma.com/rtd0f6ka',roster:'sfSpeakers'},
]) {
  const venue='AWS Builder Loft, 525 Market St, San Francisco';
  for (const required of [e.title,e.marker,e.registration,venue,...(e.start ? ['6:00 PM'] : [])]) if (!sfText.includes(required)) throw new Error('SF source drift: '+required);
  const ref=source(e.id,site+'/san-francisco',`${e.title}. ${e.marker}. ${venue}.`,e.id,'event');
  events.push({id:e.id,title:e.title,city:'San Francisco',timezone:'America/Los_Angeles',date:e.date,
    venue,start:e.start ?? null,registration_url:e.registration,source_ids:[ref]});
  for (const [i,s] of constant(e.roster).entries()) {
    const sid=slug(s.name); const sr=source(e.id+'-'+sid,site+'/san-francisco',`${s.name}, ${s.org}. ${s.talk}`,e.id,'speaker');
    speakers.push({id:sid,name:s.name,company:s.org,event_ids:[e.id],talk_title:s.talk,source_ids:[sr]});
    sessions.push({id:e.id+'-'+i,event_id:e.id,title:s.talk,kind:'talk',speaker_id:sid,topics:topics(s.talk),source_ids:[sr]});
  }
}
const faqs = constant('faqs').map((f,i) => {
  const sid = source('faq-'+i,site+'/london-2026#faq',f.question+'\n'+f.answer,london,'faq');
  return {id:'faq-'+i,question:f.question,answer:f.answer,event_id:london,source_ids:[sid]};
});
const conductAnswer = faqs.find(f => /code of conduct/i.test(f.question))?.answer
  || 'Read the code of conduct at https://agentengineering.world/code-of-conduct';
const conductSource = source('code-of-conduct',site+'/code-of-conduct',conductAnswer,london,'conduct');
const themes = [
  {id:'agent-optimization',title:'Agent Optimization',command:'optimize',
    description:'Automatically optimize agents across all layers: prompts, RAG, protocols, memory, and context.'},
  {id:'agent-experience',title:'Agent Experience (AX)',command:'design-ax',
    description:'Designing machine-readable interfaces, environments, and feedback loops that shape Agent Experience.'},
  {id:'agentic-coding',title:'Agentic Coding',command:'future-code',
    description:'How software development evolves as agents become first-class contributors to the SDLC.'},
  {id:'agentic-business-models',title:'Agentic Business Models',command:'business-models',
    description:'Defining the business models for agentic AI. Does SaaS still work, or is FDE the only way forward? Explore and share business models.'},
];
for (const theme of themes) {
  if (!tracksText.includes(theme.title) || !tracksText.includes(theme.description)) {
    throw new Error('Program theme drift: '+theme.id);
  }
  source('theme-'+theme.id,site+'/london-2026#tracks',theme.title+'\n'+theme.description,london,'theme');
}
const sponsors = [
  {id:'arize-ai',name:'Arize AI',url:'https://arize.com',city:'San Francisco',
    blurb:'AI observability and evaluation for agents in production.'},
  {id:'cocoindex',name:'CocoIndex',url:'https://cocoindex.io',city:'San Francisco',
    blurb:'Open-source data indexing that keeps agent context fresh.'},
];
for (const sponsor of sponsors) {
  if (!sponsorText.includes(sponsor.name) || !sponsorText.includes(sponsor.url) || !sponsorText.includes(sponsor.blurb)) {
    throw new Error('Sponsor drift: '+sponsor.id);
  }
  source('sponsor-'+sponsor.id,site+'/san-francisco',sponsor.name+'. '+sponsor.blurb,null,'sponsor');
}
const support_options = [
  {id:'refreshments',title:'Refreshments',
    blurb:'Help with arrival tea and pastries or lunch. A warm, practical way to be present without a trade-show package.'},
  {id:'after-party',title:'After-party / drinks',
    blurb:'Support an evening gathering after the talks, if we run one. Ideal for hallway conversations and informal recognition.'},
  {id:'recording',title:'Recording support',
    blurb:'A professional videographer already records the talks. Help fund editing and publishing them, with credit on the released recordings and related posts.'},
];
for (const option of support_options) {
  if (!sponsorsPage.includes(option.title) || !sponsorsPage.includes(option.blurb)) {
    throw new Error('Support option drift: '+option.id);
  }
  source('support-'+option.id,site+'/support',option.title+'\n'+option.blurb,london,'sponsorship');
}
source('hq',site+'/agent-engineering-hq','Agent Engineering HQ organises practitioner events on building, evaluating and operating production AI agents, with communities in San Francisco and London.',null);
source('contact',site+'/',`Public organiser contact: ${constant('ORGANISER_EMAIL')}`,null);
source('sponsor-contact',site+'/support',`Sponsorship enquiry: ${constant('ORGANISER_EMAIL')}`,null,'sponsorship');
// Agent Engineering HQ page content and the published organiser card.
read('src/pages/AgentEngineeringHQ.tsx');
read('src/components/ManifestoSection.tsx');
read('src/components/AgentEngineeringMindsetSection.tsx');
read('src/components/FurtherReadingSection.tsx');
read('src/components/WhatIsAgentEngSection.tsx');
read('src/components/FounderCLISection.tsx');
const hqUrl = site+'/agent-engineering-hq';
const manifesto = jsxTexts('src/components/ManifestoSection.tsx', 'p');
if (manifesto.length !== 5 || !manifesto[0].startsWith('Agents are not features')) throw new Error('Manifesto drift');
const mindset = pickFields('mindsetPrinciples', ['title', 'description']);
if (mindset.length < 1) throw new Error('Mindset drift');
const further_reading = constant('readings').map(r => ({title:r.title, date:r.date, url:r.link}));
const readingIntro = only(jsxTexts('src/components/FurtherReadingSection.tsx', 'p'),
  t => t.startsWith('Agent Engineering surfaced'), 'further reading intro');
const hqSummary = jsxAttribute('src/pages/AgentEngineeringHQ.tsx', 'meta', 'property', 'og:description', 'content');
const citiesText = only(jsxTexts('src/pages/AgentEngineeringHQ.tsx', 'p'),
  t => t.startsWith('Agent Engineering HQ runs San Francisco'), 'cities paragraph');
const hqSources = {
  manifesto: source('hq-manifesto', hqUrl+'#manifesto', manifesto.join('\n\n'), null, 'hq'),
  mindset: source('hq-mindset', hqUrl+'#mindset', mindset.map(m => m.title+': '+m.description).join('\n'), null, 'hq'),
  reading: source('hq-further-reading', hqUrl, further_reading.map(r => `${r.date} ${r.title} ${r.url}`).join('\n'), null, 'hq'),
};
const hq_content = {url:hqUrl, summary:hqSummary, cities:citiesText, manifesto, mindset,
  further_reading_intro:readingIntro, further_reading, source_ids:Object.values(hqSources)};
const definition = only(jsxTexts('src/components/WhatIsAgentEngSection.tsx', 'p'),
  t => t.startsWith('Agent Engineering is the discipline'), 'definition');
const founder = 'src/components/FounderCLISection.tsx';
const chairName = only(jsxTexts(founder, 'h3'), t => /^\[ .+ \]$/.test(t), 'chair name').slice(2, -2);
const chairTitle = only(jsxTexts(founder, 'p'), t => t.startsWith('Conference Chair'), 'chair title');
const chairBio = only(jsxTexts(founder, 'div'), t => t.startsWith('Building the bridge'), 'chair bio');
const organiserName = only(jsxTexts(founder, 'p'), t => t === 'Superagentic AI', 'organiser name');
const organiserBlurb = only(jsxTexts(founder, 'p'), t => t.startsWith('Advancing the Agent Engineering'), 'organiser blurb');
const chairLinks = nestedConstant(founder, 'links');
const organiserUrl = only(chairLinks, l => l.label === organiserName, 'organiser link').url;
// Associates are published on the homepage chair card (and the /support Team section).
const associatesText = fs.readFileSync(path.join(root, founder), 'utf8');
const associateMatches = [];
walk(trees.get(founder), n => {
  if (!ts.isArrayLiteralExpression(n) || !n.elements.length) return;
  if (!n.elements.every(e => ts.isObjectLiteralExpression(e))) return;
  const rows = evaluate(n);
  if (rows.every(r => Object.keys(r).join() === 'name,url' && r.url.startsWith('https://www.linkedin.com/'))) {
    associateMatches.push(...rows.map(r => ({name:r.name, url:r.url})));
  }
});
if (!associatesText.includes('associates') || associateMatches.length < 1) throw new Error('Associates drift');
const aboutSource = source('about', site+'/', [definition, `Organised by ${organiserName}: ${organiserBlurb}`,
  `${chairName}, ${chairTitle}. ${chairBio}`,
  `Associates: ${associateMatches.map(a => a.name).join(', ')}`].join('\n'), null, 'about');
const about = {definition, organiser:{name:organiserName, url:organiserUrl, blurb:organiserBlurb},
  chair:{name:chairName, title:chairTitle, bio:chairBio, links:chairLinks.map(l => ({label:l.label, url:l.url}))},
  associates:associateMatches,
  contact_email:constant('ORGANISER_EMAIL'), source_ids:[aboutSource]};
// Event-day guide (/guide), hero tagline, the "truly yours" block and venue
// directions. JSX prose only; links come from literal href/label pairs.
const clean = text => text.replace(/\s*\u2014\s*/g, ', ').replace(/\u2013/g, '-')
  .replace(/&amp;/g, '&').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').replace(/\s+([.,;:])/g, '$1').trim();
const guideFile = 'src/pages/Guide.tsx';
read(guideFile);
read('src/lib/event-day.ts');
read('src/components/HeroSection.tsx');
read('src/components/WhyDifferentSection.tsx');
read('src/components/VenueSection.tsx');
read('src/components/VenueWalkVideo.tsx');
read('src/pages/Agenda.tsx');
const indexText = read('src/pages/Index.tsx');
function declaration(file, name) {
  let found = null;
  walk(trees.get(file), n => {
    if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === name) found = n.initializer;
  });
  if (!found) throw new Error(`Missing ${name} in ${file}`);
  return found;
}
// Text of a JSX node; ext(href, label) calls contribute their label and a link.
function richText(n, links) {
  if (ts.isJsxText(n)) return n.text;
  if (ts.isJsxExpression(n)) {
    const e = n.expression;
    if (!e) return '';
    if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return e.text;
    if (ts.isCallExpression(e) && ts.isIdentifier(e.expression) && e.expression.text === 'ext') {
      const [href, label] = e.arguments.map(evaluate);
      links.push({label, url: href, at: null});
      return '\u0000' + (links.length - 1) + '\u0000' + label;
    }
    return '';
  }
  if (ts.isJsxElement(n) || ts.isJsxFragment(n)) return n.children.map(c => richText(c, links)).join('');
  return '';
}
const guideSections = declaration(guideFile, 'sections').elements.map(element => {
  const prop = key => element.properties.find(p => ts.isPropertyAssignment(p) && p.name.text === key);
  const id = evaluate(prop('id').initializer);
  const title = evaluate(prop('title').initializer);
  const paragraphs = [];
  const links = [];
  walk(prop('body').initializer, n => {
    if (tagName(n) !== 'p') return;
    const raw = richText(n, links);
    // Attribute each link to the last "<Name> on" before it ("Shashi on X or LinkedIn").
    let owner = null;
    raw.split(/\u0000(\d+)\u0000/).forEach((part, i, parts) => {
      if (i % 2) { links[Number(part)].owner = owner; return; }
      const hits = [...part.replace(/[\u0000\d]/g, '').matchAll(/([A-Z][\w.]+) on\s*$|([A-Z][\w.]+) on\b/g)];
      if (hits.length) { const h = hits[hits.length - 1]; owner = h[1] || h[2]; }
    });
    paragraphs.push(clean(raw.replace(/\u0000\d+\u0000/g, '')));
  });
  if (!id || !title || !paragraphs.length) throw new Error('Guide section drift: ' + id);
  return {id, title: clean(title), paragraphs,
    links: links.map(l => ({label: l.owner ? `${l.owner} on ${l.label}` : l.label, url: l.url}))};
});
const expectedGuide = ['arriving','getting-here','registration','social-area','speaker-area','lunch',
  'qna','photography','phones','seating','help','after'];
if (guideSections.map(s => s.id).join() !== expectedGuide.join()) {
  throw new Error('Guide sections changed: ' + guideSections.map(s => s.id).join());
}
const guideFacts = evaluate(declaration(guideFile, 'facts')).map(f => ({label: clean(f.label), value: clean(f.value)}));
const fact = label => only(guideFacts, f => f.label === label, 'guide fact '+label).value;
const guideVenue = fact('Venue');
if (guideVenue !== events[0].venue) throw new Error('Guide venue drift: ' + guideVenue);
const walkUrl = evaluate(declaration('src/components/VenueWalkVideo.tsx', 'WATCH_URL'));
if (!/^https:\/\/www\.youtube\.com\/watch\?v=[\w-]+$/.test(walkUrl)) throw new Error('Walk video drift');
const walkText = fs.readFileSync(path.join(root, 'src/components/VenueWalkVideo.tsx'), 'utf8');
const walkLabel = (walkText.match(/aria-label="Play video: ([^"]+)"/) || [])[1];
if (!walkLabel) throw new Error('Walk video label drift');
guideSections.find(s => s.id === 'getting-here').links.push({label: clean(walkLabel.replace(/^./, c => c.toUpperCase())), url: walkUrl});
const agendaLine = only(jsxTexts('src/pages/Agenda.tsx', 'p'), t => /please be seated by/.test(t), 'agenda seated line');
const seatedBy = (agendaLine.match(/please be seated by (\d{1,2}:\d{2})/) || [])[1];
if (!seatedBy) throw new Error('Seated-by drift');
const section = id => only(guideSections, s => s.id === id, 'guide section '+id);
const firstSentence = text => clean(text).match(/^.*?\.(?=\s|$)/)[0];
const venueParas = jsxTexts('src/components/VenueSection.tsx', 'p').map(clean);
// After the event the homepage venue block dropped its "Best way in" and
// registration lines; the guide keeps the registration wording.
const bestWayPara = venueParas.filter(t => t.startsWith('Best way in:'));
if (bestWayPara.length > 1) throw new Error('Expected at most one best way in');
const bestWay = bestWayPara.length ? bestWayPara[0].replace(/^Best way in:\s*/, '') : null;
const venueRegPara = venueParas.filter(t => t.startsWith('Registration is on the left'));
const venueRegistration = firstSentence(venueRegPara.length ? venueRegPara[0] : section('registration').paragraphs[0]);
const venueGetting = only(pickFields('venueDetails', ['title', 'detail']), d => d.title === 'Getting There', 'getting there').detail;
const helpSection = section('help');
const onSiteSentence = firstSentence(helpSection.paragraphs[0]);
const onSite = (onSiteSentence.match(/^Find (.+)\.$/) || [])[1];
if (!onSite) throw new Error('Help drift');
const associatesOnSite = (section('registration').paragraphs.join(' ').match(/([A-Z]\w+(?:, [A-Z]\w+)*) \(our Associates\)/) || [])[1];
if (!associatesOnSite) throw new Error('Associates on site drift');
const helpContacts = {
  on_site: onSite.split(/, | or /).map(name => name.replace(/^the /, '')).map(name => ({
    name: name.replace(/^./, c => c.toUpperCase()),
    role: associatesOnSite.split(', ').includes(name) ? 'Associate' : null})),
  online: helpSection.links,
};
for (const want of ['https://x.com/Shashikant86', 'https://www.linkedin.com/in/shashikantjagtap',
  'https://x.com/AgentEngHQ', 'https://www.linkedin.com/company/agent-engineering-hq/']) {
  if (!helpContacts.online.some(l => l.url === want)) throw new Error('Help contact drift: ' + want);
}
// heroLead(phase): phase === "today" ? A : phase === "after" ? B : ... : default.
const heroLead = {};
let cond = declaration('src/lib/event-day.ts', 'heroLead').body;
while (ts.isConditionalExpression(cond)) {
  heroLead[cond.condition.right.text] = clean(cond.whenTrue.text);
  cond = cond.whenFalse;
}
heroLead.before = clean(cond.text);
if (Object.keys(heroLead).sort().join() !== 'after,before,eve,today') throw new Error('heroLead drift');
const tagline = clean(only(jsxTexts('src/components/HeroSection.tsx', 'span'),
  t => t.startsWith('There are many Agent conferences'), 'hero tagline'));
if (tagline !== 'There are many Agent conferences. This one is truly yours.') throw new Error('Tagline drift: ' + tagline);
const guideIntro = clean(only(jsxTexts(guideFile, 'p'), t => t.startsWith(tagline), 'guide intro'));
const trulyTitle = clean(only(jsxTexts('src/components/WhyDifferentSection.tsx', 'h3'),
  t => t.startsWith('Why this one is'), 'truly yours title'));
const trulyText = clean(only(jsxTexts('src/components/WhyDifferentSection.tsx', 'p'),
  t => t.startsWith('Most agent conferences'), 'truly yours text'));
const seating = section('seating').paragraphs[0];
const fullyBooked = firstSentence(seating);
if (!/fully booked/.test(fullyBooked)) throw new Error('Registration status drift: ' + fullyBooked);
if (/<TicketsSection\b/.test(indexText)) throw new Error('Homepage promotes tickets again; review registration status');
const guideUrl = site + '/london-2026/guide';
const guideSourceIds = [
  source('guide', guideUrl, [guideIntro, ...guideFacts.map(f => `${f.label}: ${f.value}`)].join('\n'), london, 'guide'),
  ...guideSections.map(s => source('guide-' + s.id, guideUrl + '#' + s.id,
    s.title + '\n' + s.paragraphs.join('\n'), london, 'guide')),
];
const venueSource = source('london-venue-directions', site + '/london-2026',
  [...(bestWay ? [`Best way in: ${bestWay}`] : []), venueGetting, venueRegistration, `Walk video: ${walkUrl}`].join('\n'), london, 'venue');
const taglineSource = source('truly-yours', site + '/#truly-yours',
  [tagline, trulyTitle, trulyText].join('\n'), london, 'about');
const guide = {event_id: london, url: guideUrl, title: clean(evaluate(declaration(guideFile, 'TITLE'))),
  description: clean(evaluate(declaration(guideFile, 'DESCRIPTION'))), intro: guideIntro,
  hero_lead: heroLead, facts: [...guideFacts.slice(0, 4), {label: 'Be seated by', value: seatedBy}, ...guideFacts.slice(4)],
  sections: guideSections, help: helpContacts,
  venue: {address: guideVenue, best_way_in: bestWay, getting_there: venueGetting,
    walk_video_url: walkUrl, registration: venueRegistration,
    doors: fact('Doors'), arrive: fact('Arrive'), seated_by: seatedBy, programme_starts: fact('Programme starts'),
    source_ids: [venueSource]},
  source_ids: guideSourceIds};
Object.assign(events[0], {tagline, registration_status: 'fully_booked', registration_note: fullyBooked});
events[0].source_ids.push(guideSourceIds[0] , taglineSource);
const truly_yours = {tagline, title: trulyTitle, text: trulyText, source_ids: [taglineSource]};
// Agent-to-Agent (A2A) Talks (/agent-to-agent): AI-generated videos, kept apart
// from speakers, talks and sessions on purpose.
const a2aDataFile = 'src/data/agentToAgent.ts';
const a2aPageFile = 'src/pages/AgentToAgent.tsx';
read(a2aDataFile); read(a2aPageFile);
const a2aText = fs.readFileSync(path.join(root, a2aDataFile), 'utf8');
const a2aRows = [...a2aText.matchAll(/\{\s*session:\s*"(\d+)",\s*title:\s*"([^"]+)",\s*videoId:\s*"([^"]+)",\s*tag:\s*"([^"]+)"(?:,\s*durationSec:\s*(\d+))?/g)];
if (a2aRows.length !== (a2aText.match(/\bsession:\s*"/g) || []).length || !a2aRows.length)
  throw new Error('A2A talk data shape changed');
const a2aUrl = site + '/agent-to-agent';
const a2aDisclaimer = clean(only(jsxTexts(a2aPageFile, 'p'), t => t.startsWith('These videos are produced'), 'A2A disclaimer'));
const a2aIntro = clean(only(jsxTexts(a2aPageFile, 'p'), t => t.startsWith('A series of short'), 'A2A intro'));
const a2aTitle = clean(only(jsxTexts(a2aPageFile, 'span'), t => t.startsWith('Agent-to-Agent'), 'A2A title'));
const mmss = n => `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`;
const a2aVideos = a2aRows.map(([, session, title, videoId, tag, dur]) => ({
  id: 'a2a-' + session, session, title: clean(title), youtube_id: videoId,
  url: 'https://www.youtube.com/watch?v=' + videoId, tag,
  duration_sec: dur ? Number(dur) : null, duration: dur ? mmss(Number(dur)) : null}));
const a2aSource = source('a2a-talks', a2aUrl, [a2aTitle, a2aIntro, a2aDisclaimer,
  ...a2aVideos.map(v => `${v.session} ${v.title} (${v.tag})`)].join('\n'), null, 'a2a-talks');
const a2a_talks = {url: a2aUrl, title: a2aTitle, intro: a2aIntro, disclaimer: a2aDisclaimer,
  videos: a2aVideos, source_ids: [a2aSource]};
// Gallery (/gallery, /gallery/<slug>) and London recordings (/london-2026/videos),
// mirrored from src/data/talks.ts. talks.ts derives its rows from agenda,
// speakers, sf-code-engineering and the A2A data; we rebuild them from those
// literals (never executing site code) and fail if the mapping drifts.
const talksFile = 'src/data/talks.ts';
const talksText = read(talksFile);
const sfCodeFile = 'src/data/sf-code-engineering.ts';
read(sfCodeFile);
read('src/data/events.ts');
for (const needle of [
  'slug: `london-2026-${slugify(slot.title)}`.slice(0, 90).replace(/-$/, "")',
  'status: "recording-coming-soon"',
  'slug: `sf-code-engineering-${slugify(s.talk!.title)}`.slice(0, 90).replace(/-$/, "")',
  'topics: ["Code", "Harness"],',
  'status: "upcoming"',
  'slug: `a2a-${v.session}-${slugify(v.title)}`',
  'aiGenerated: true',
  'export const londonVideos: Talk[] = [londonWelcome, ...londonTalks];',
  'export const sfGallery: Talk[] = sfRecordings;',
  'export const talks: Talk[] = [...londonVideos, ...sfRecordings, ...a2aTalks];',
]) if (!talksText.includes(needle)) throw new Error('talks.ts drift: ' + needle);
const londonBlock = talksText.slice(talksText.indexOf('const londonTalks'), talksText.indexOf('const londonWelcome'));
const sfCodeBlock = talksText.slice(talksText.indexOf('export const codeEngineeringTalks'), talksText.indexOf('const sfRecordings'));
if (/youtubeId|transcript/.test(londonBlock + sfCodeBlock)) throw new Error('talks.ts now publishes recordings or transcripts; mirror them');
const galleryPagesText = read('src/pages/Gallery.tsx');
if (!galleryPagesText.includes('const all = [...londonVideos, ...sfGallery];')) throw new Error('Gallery page drift');
const londonVideosPage = site + '/london-2026/videos';
read('src/pages/LondonVideos.tsx');
const talkSlug = text => text.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const siteDisciplines = constant('disciplines').map(d => ({id: d.id, title: clean(d.title), short: d.short, description: clean(d.description)}));
const shortFor = slug => siteDisciplines.filter(d => (speakerDisciplines[slug] || []).includes(d.id)).map(d => d.short);
const eventIdFor = id => id === 'london-2026' ? london : id;
const literalTalk = r => ({slug: r.slug, title: r.title, kind: r.kind, city: r.city, event_id: eventIdFor(r.eventId),
  event_name: r.eventName, event_url: site + r.eventHref, date: r.date, speaker: null, topics: r.topics,
  youtube_id: r.youtubeId ?? null, transcript: r.transcript ? clean(r.transcript) : null,
  ai_generated: false, status: r.status, session_id: null});
const talks = [];
const welcome = constant('londonWelcome');
talks.push({...literalTalk(welcome), gallery: 'london'});
for (const slot of constant('agenda').filter(a => a.kind === 'talk' && a.speakerSlug)) {
  const sp = roster.find(r => r.slug === slot.speakerSlug);
  const slug = `london-2026-${talkSlug(slot.title)}`.slice(0, 90).replace(/-$/, '');
  talks.push({slug, title: slot.title, kind: 'talk', city: 'London', event_id: london,
    event_name: 'Agent Engineering London 2026', event_url: site + '/london-2026', date: '2026-10-16',
    speaker: {name: sp.name, role: sp.role, company: sp.company, slug: sp.slug}, topics: shortFor(sp.slug),
    youtube_id: null, transcript: null, ai_generated: false, status: 'recording-coming-soon', session_id: slot.id, gallery: 'london'});
}
for (const r of constant('sfRecordings')) talks.push({...literalTalk(r), gallery: 'san-francisco'});
for (const v of a2aVideos) {
  talks.push({slug: `a2a-${v.session}-${talkSlug(v.title)}`, title: v.title, kind: 'a2a', city: 'Online',
    event_id: null, event_name: 'Agent-to-Agent (A2A) Talks', event_url: a2aUrl, date: null, speaker: null,
    topics: [v.tag], youtube_id: v.youtube_id, transcript: null, ai_generated: true, status: 'recorded', session_id: null, gallery: 'a2a'});
}
// Code Engineering SF talks are listed on /san-francisco only: no gallery page.
const codeSpeakers = constant('codeEngineeringSpeakers');
for (const s of codeSpeakers) {
  const slug = `sf-code-engineering-${talkSlug(s.talk.title)}`.slice(0, 90).replace(/-$/, '');
  talks.push({slug, title: s.talk.title, kind: 'talk', city: 'San Francisco', event_id: 'sf-code-engineering-2026',
    event_name: 'Code Engineering San Francisco', event_url: site + '/san-francisco', date: '2026-10-27',
    speaker: {name: s.name, role: s.role, company: s.company, slug: s.slug}, topics: ['Code', 'Harness'],
    youtube_id: null, transcript: null, ai_generated: false, status: 'upcoming', session_id: null, gallery: null});
}
if (new Set(talks.map(t => t.slug)).size !== talks.length) throw new Error('Duplicate talk slugs');
for (const t of talks) {
  t.url = t.gallery ? site + '/gallery/' + t.slug : site + '/san-francisco';
  t.source_ids = [source('talk-' + t.slug, t.url, [t.title, t.speaker ? `${t.speaker.name}, ${t.speaker.role} at ${t.speaker.company}` : null,
    t.event_name, t.ai_generated ? 'AI-generated video.' : null, t.status].filter(Boolean).join('\n'), t.event_id, t.kind === 'a2a' ? 'a2a-talks' : 'talk')];
}
source('london-videos', londonVideosPage, 'Agent Engineering London 2026 recordings: ' + welcome.title +
  ' (https://www.youtube.com/watch?v=' + welcome.youtubeId + '). Talk recordings coming soon.', london, 'recordings');
// SF Code Engineering roster: roles and links from sf-code-engineering.ts.
for (const s of codeSpeakers) {
  const sp = speakers.find(p => p.id === s.slug && p.event_ids.includes('sf-code-engineering-2026'));
  if (!sp || sp.name !== s.name || sp.talk_title !== s.talk.title) throw new Error('SF Code Engineering roster drift: ' + s.slug);
  Object.assign(sp, {role: s.role, company: s.company, company_url: s.companyUrl || null,
    links: s.links ? Object.fromEntries(Object.entries(s.links).filter(([, v]) => v)) : null});
}
// Next and previous editions from src/data/events.ts.
const conferencesData = constant('conferences');
const nextConf = conferencesData.find(c => c.status === 'announced' || c.status === 'upcoming');
const prevConf = conferencesData.find(c => c.status === 'past');
const site_links = {next_event: nextConf ? {name: nextConf.name, when: nextConf.when, url: site + nextConf.href} : null,
  previous_event: prevConf ? {name: prevConf.name, when: prevConf.when, url: site + prevConf.href} : null,
  london_2026: site + '/london-2026', gallery: site + '/gallery', london_videos: londonVideosPage, agenteng: site + '/agenteng'};
for (const e of events) e.page_url = e.id === london ? site + '/london-2026' : e.city === 'San Francisco' ? site + '/san-francisco' : site + '/london';
const source_hash=hash.digest('hex');
const catalogue={schema_version:1,version:'website-'+source_hash.slice(0,12),published_at:new Date().toISOString(),
  source_commit:execFileSync('git',['-C',root,'rev-parse','HEAD'],{encoding:'utf8'}).trim(),source_hash,
  events,speakers,sessions,faqs,sponsors,support_options,themes,hq:hq_content,about:{...about,truly_yours},guide,a2a_talks,talks,disciplines:siteDisciplines,site_links,sources};
fs.mkdirSync(path.dirname(output),{recursive:true});
fs.writeFileSync(output,JSON.stringify(catalogue,null,2)+'\n');
console.log(`Exported ${events.length} events, ${speakers.length} speakers, ${sessions.length} sessions, ${faqs.length} faqs, ${guide.sections.length} guide sections, ${a2aVideos.length} A2A talks, ${talks.filter(t => t.gallery).length} gallery items, ${talks.length} talks to ${output}`);
