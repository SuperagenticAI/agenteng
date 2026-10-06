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
values.set('speakers', [...roster].sort((a,b) => b.announcedOn.localeCompare(a.announcedOn)));
values.set('whoIsSpeakingAnswer', 'The lineup: ' + roster.map(
  s => `${s.name}, ${s.role} at ${s.company}`).join('; ') + '. See the published speakers page.');
read('src/components/FAQSection.tsx');
const site = 'https://agentengineering.world';
const sources = [];
function source(id, url, text, event_id, kind = 'document') {
  sources.push({id, url, text, event_id, kind}); return id;
}
const london = 'agenteng-london-2026';
const londonSource = source(london, site+'/', 'AgentEng London 2026. 16 October 2026. Everyman Canary Wharf, Crossrail Place, London E14 5AR.', london, 'event');
const ticketSource = source('london-ticket-terms', site+'/#tickets',
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
  const id = source('speaker-'+s.slug,site+'/speakers#'+s.slug,
    `${s.name}, ${s.role} at ${s.company}. ${s.talk?.title ?? 'Talk not announced'}. ${abstract ?? ''}`,london,'speaker');
  return {id:s.slug,name:s.name,role:s.role,company:s.company,
    company_url:s.companyUrl || null,note:s.note || null,location,links,projects,
    announced_on:s.announcedOn || null,disciplines,event_ids:[london],
    talk_title:s.talk?.title ?? null,abstract,source_ids:[id]};
});
const topics = text => [...new Set(['memory','evaluation','harness','context','security','voice','coding','mcp','acp','inference']
  .filter(t => text.toLowerCase().includes(t === 'evaluation' ? 'eval' : t)))];
const sessions = constant('agenda').map((s,i) => {
  const speaker = speakers.find(p => p.id === s.speakerSlug);
  const id = source(`london-session-${i}`,site+'/agenda',
    `${s.time} ${s.title}. ${speaker?.name ?? ''}. ${speaker?.abstract ?? s.note ?? ''}`,london,'session');
  return {id:`${london}-${i}`,event_id:london,title:s.title,kind:s.kind,
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
  const sid = source('faq-'+i,site+'/#faq',f.question+'\n'+f.answer,london,'faq');
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
  source('theme-'+theme.id,site+'/#program',theme.title+'\n'+theme.description,london,'theme');
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
    blurb:'Help with filming, editing, or publishing the talks. Credit on the released recordings and related posts.'},
];
for (const option of support_options) {
  if (!sponsorsPage.includes(option.title) || !sponsorsPage.includes(option.blurb)) {
    throw new Error('Support option drift: '+option.id);
  }
  source('support-'+option.id,site+'/sponsorships',option.title+'\n'+option.blurb,london,'sponsorship');
}
source('hq',site+'/agent-engineering-hq','Agent Engineering HQ organises practitioner events on building, evaluating and operating production AI agents, with communities in San Francisco and London.',null);
source('contact',site+'/',`Public organiser contact: ${constant('ORGANISER_EMAIL')}`,null);
source('sponsor-contact',site+'/sponsorships',`Sponsorship enquiry: ${constant('ORGANISER_EMAIL')}`,null,'sponsorship');
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
const aboutSource = source('about', site+'/', [definition, `Organised by ${organiserName}: ${organiserBlurb}`,
  `${chairName}, ${chairTitle}. ${chairBio}`].join('\n'), null, 'about');
const about = {definition, organiser:{name:organiserName, url:organiserUrl, blurb:organiserBlurb},
  chair:{name:chairName, title:chairTitle, bio:chairBio, links:chairLinks.map(l => ({label:l.label, url:l.url}))},
  contact_email:constant('ORGANISER_EMAIL'), source_ids:[aboutSource]};
const source_hash=hash.digest('hex');
const catalogue={schema_version:1,version:'website-'+source_hash.slice(0,12),published_at:new Date().toISOString(),
  source_commit:execFileSync('git',['-C',root,'rev-parse','HEAD'],{encoding:'utf8'}).trim(),source_hash,
  events,speakers,sessions,faqs,sponsors,support_options,themes,hq:hq_content,about,sources};
fs.mkdirSync(path.dirname(output),{recursive:true});
fs.writeFileSync(output,JSON.stringify(catalogue,null,2)+'\n');
console.log(`Exported ${events.length} events, ${speakers.length} speakers, ${sessions.length} sessions, ${faqs.length} faqs to ${output}`);
