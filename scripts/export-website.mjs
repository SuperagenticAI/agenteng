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
const hash = crypto.createHash('sha256');
function read(file) {
  const text = fs.readFileSync(path.join(root, file), 'utf8');
  hash.update(file).update(text);
  const tree = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true,
    file.endsWith('tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
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
read('src/data/agenda.ts');
read('src/data/speakers.ts');
read('src/data/tickets.ts');
read('src/data/london-events.ts');
read('src/data/contact.ts');
const sfText = read('src/pages/SanFrancisco.tsx');
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
const events = [{id:london,title:'AgentEng London 2026',city:'London',timezone:'Europe/London',
  date:'2026-10-16',venue:'Everyman Canary Wharf, Crossrail Place, London E14 5AR',
  start:'2026-10-16T08:00:00+01:00',end:'2026-10-16T16:30:00+01:00',
  registration_url:constant('LUMA_EVENT_URL'),offers,speaker_submission_status:'invited_only',source_ids:[londonSource,ticketSource,calendarSource,policySource]}];
const speakers = roster.map(s => {
  const abstract = s.talk ? [].concat(s.talk.abstract).join('\n\n') : null;
  const id = source('speaker-'+s.slug,site+'/speakers#'+s.slug,
    `${s.name}, ${s.role} at ${s.company}. ${s.talk?.title ?? 'Talk not announced'}. ${abstract ?? ''}`,london,'speaker');
  return {id:s.slug,name:s.name,role:s.role,company:s.company,event_ids:[london],
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
for (const [i,f] of constant('faqs').entries()) source('faq-'+i,site+'/#faq',f.question+'\n'+f.answer,london,'faq');
source('hq',site+'/agent-engineering-hq','Agent Engineering HQ organises practitioner events on building, evaluating and operating production AI agents, with communities in San Francisco and London.',null);
source('contact',site+'/',`Public organiser contact: ${constant('ORGANISER_EMAIL')}`,null);
const source_hash=hash.digest('hex');
const catalogue={schema_version:1,version:'website-'+source_hash.slice(0,12),published_at:new Date().toISOString(),
  source_commit:execFileSync('git',['-C',root,'rev-parse','HEAD'],{encoding:'utf8'}).trim(),source_hash,events,speakers,sessions,sources};
fs.mkdirSync(path.dirname(output),{recursive:true});
fs.writeFileSync(output,JSON.stringify(catalogue,null,2)+'\n');
console.log(`Exported ${events.length} events, ${speakers.length} speakers, ${sessions.length} sessions to ${output}`);
