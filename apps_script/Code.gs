/**
 * Coimbatore 360 bridge (Coimbatore district page கோயம்புத்தூர் 360) – copied from the Namakkal News360 bridge.
 * It must run in its OWN Google account with its OWN Sheet, Drive folder and Cloudinary account (never the Namakkal ones).
 * The GitHub posting job talks to this web app to:
 *   - read the queue of stories from the "Coimbatore 360 Log" Sheet
 *   - get the Instagram token (kept here, refreshed automatically every week)
 *   - fetch a recorded human voice for a reel (Drive folder "Voice")
 *   - after posting: update the Sheet + the story's Google Doc and email the owner
 *
 * Setup (once): see README.md in the GitHub repository, section "Apps Script".
 * Script properties used: BRIDGE_KEY, IG_TOKEN_TRICHY, (auto) VOICE_FOLDER_ID, optional ALLOWED_SENDERS
 * E-mail subjects use the tag TRICHY360 (not NEWS360) so the Namakkal bridge never reads Coimbatore mails and the other way round.
 */
// ---- OWNER SETS THESE (new Google account for Coimbatore 360; never the Namakkal Sheet / folder / Gmail) ----
var SHEET_ID = '1u_SUuFW8XLP2C5J2bI6fFgMMbHqOcadXWWyN0LcitIE';      // SALEM: the id of the new "Trichy 360 Log" Sheet - REQUIRED (never the Coimbatore Sheet)                 // id of the new "Coimbatore 360 Log" Sheet (tab "News", same 31 columns)
var TAB = 'News';
var ROOT_FOLDER_ID = '1InZDYxs2ej5r3vgaU7iw9XYBQTiGRarK';      // SALEM: the id of the new Drive folder "Trichy 360" - REQUIRED    // id of the new Drive folder "Coimbatore 360" (prompt files, Voice folder)
var OWNER_EMAIL = 'nammarasipuram2805@gmail.com';           // the owner's Gmail that receives the reports and may send stories / images
var SHEET_LINK = 'https://docs.google.com/spreadsheets/d/' + SHEET_ID + '/edit';

// 1-based column numbers in the News tab
var C = {
  story_id: 1, researched: 2, published: 3, headline_ta: 4, headline_en: 5, category: 6, location: 7,
  importance: 8, verification: 9, source: 10, other_sources: 11, review_page: 12, doc: 13, notion: 14,
  caption: 15, email_sent: 16, gmail_id: 17, review: 18, post_to: 19, reel: 20, reel_script: 21,
  slides_spec: 22, post_status: 23, posted_at: 24, spare_link: 25, trichy_link: 26, reel_link: 27, notes: 28,
  batch: 29, prompts: 30, images: 31
};
var NCOLS = 31;
var CLOUD_NAME = 'vkghshc8';       // OWNER SETS: the new Cloudinary account's cloud name (same as GitHub secret CLOUDINARY_CLOUD)
var UPLOAD_PRESET = 'trichy360';                 // OWNER SETS: unsigned upload preset in that account (same as GitHub secret CLOUDINARY_PRESET)
var MIN_IMAGES = 1;     // Coimbatore: ONE image per reel
var EXPIRE_HOURS = 2;   // owner request 24 Oct: after 3 hours without the owner's images, automatic images are made and the story is posted
var COLLAB_USERNAME = '';        // Coimbatore: one page, no collaborator
var PAGE_LABEL = { trichy: 'திருச்சி 360' };
var PAGE_COL = { trichy: C.trichy_link };

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
function props_() { return PropertiesService.getScriptProperties(); }
function authorized_(e) {
  var key = props_().getProperty('BRIDGE_KEY');
  return key && e && e.parameter && e.parameter.key === key;
}
function sheet_() { return SpreadsheetApp.openById(SHEET_ID).getSheetByName(TAB); }
function nowIst_() { return Utilities.formatDate(new Date(), 'Asia/Kolkata', 'dd MMM yyyy, HH:mm'); }

function doGet(e) {
  // owner 1 Nov: the check-box page opened from the pick e-mail (its own one-round token, never the bridge key)
  if (e && e.parameter && e.parameter.action === 'pick') return pickPage_(e);
  if (!authorized_(e)) return json_({ ok: false, error: 'unauthorized' });
  try {
    var a = e.parameter.action;
    if (a === 'queue') return json_({ ok: true, rows: queue_() });
    if (a === 'posted_rows') return json_({ ok: true, rows: postedRows_() });
    if (a === 'token') return json_({ ok: true, token: token_(e.parameter.page) });
    if (a === 'voice') return json_(voice_(e.parameter.story));
    if (a === 'recent') return json_({ ok: true, rows: recent_() });
    if (a === 'ping') return json_({ ok: true, time: nowIst_() });
    if (a === 'commentsSeen') return json_({ ok: true, ids: commentsSeen_() });
    if (a === 'autoPending') return json_({ ok: true, rows: autoPending_() });
    if (a === 'pickStatus') return json_(pickStatus_(e.parameter.round));
    return json_({ ok: false, error: 'unknown action ' + a });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function doPost(e) {
  if (!authorized_(e)) return json_({ ok: false, error: 'unauthorized' });
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var body = JSON.parse(e.postData.contents);
    if (body.action === 'commentNew') return json_(commentNew_(body));
    if (body.action === 'posted') return json_(posted_(body));
    if (body.action === 'error') return json_(error_(body));
    if (body.action === 'addStories') return json_(addStories_(body));
    if (body.action === 'archiveNews') return json_(archiveNews_(body));
    if (body.action === 'reoffer') return json_(reoffer_(body));
    if (body.action === 'setImages') return json_(setImages_(body));
    if (body.action === 'repost') return json_(repost_(body));
    if (body.action === 'pickList') return json_(pickList_(body));
    if (body.action === 'pickAuto') return json_(pickAuto_(body));
    return json_({ ok: false, error: 'unknown action ' + body.action });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

// owner 28 Oct: a posted reel the owner removed from Instagram (wrong text) is posted again: its page line is taken out of reel_link
// and the story goes back to the queue (the posting job rebuilds the reel with the corrected text). body: {ids:["RN-158"], page:"coimbatore"}
function repost_(b) {
  var sh = sheet_();
  var last = sh.getLastRow();
  var data = sh.getRange(2, 1, last - 1, NCOLS).getValues();
  var done = [];
  for (var i = 0; i < data.length; i++) {
    var r = rowObj_(data[i], i + 2);
    if ((b.ids || []).indexOf(r.story_id) < 0) continue;
    var page = b.page || targets_(r.post_to)[0];
    var label = PAGE_LABEL[page] || page;
    var keep = String(r.reel_link || '').split('\n').filter(function (l) { return l && l.indexOf(label) < 0; });
    sh.getRange(r.row, C.reel_link).setValue(keep.join('\n'));
    sh.getRange(r.row, C.post_status).setValue('Queued');
    appendNote_(sh, r.row, r.notes, nowIst_() + ' repost: ' + label + ' reel removed by the owner, posted again with corrected text');
    done.push(r.story_id);
  }
  return { ok: true, reposted: done };
}

// ------------------------------------------------------------------ queue
function rowObj_(values, rowNum) {
  var o = { row: rowNum };
  for (var k in C) o[k] = String(values[C[k] - 1] || '');
  return o;
}
/** Coimbatore: there is ONE page (கோயம்புத்தூர் 360, post_to "Coimbatore 360"), no collaborator - every story posts on it (same rule as poster/post.py pages_of). */
function targets_(postTo) {
  return ['trichy'];
}
// true when the page has its carousel (unless reel-only - Coimbatore is reel-only) and its reel
function allDone_(r) {
  return targets_(r.post_to).every(function (p) {
    var car = carouselOff_(r) || !!r[p + '_link'];
    var reel = String(r.reel_link || '').indexOf(PAGE_LABEL[p]) >= 0;
    return car && reel;
  });
}
function queue_() {
  var sh = sheet_();
  var last = sh.getLastRow();
  if (last < 2) return [];
  var data = sh.getRange(2, 1, last - 1, NCOLS).getValues();
  var out = [];
  for (var i = 0; i < data.length; i++) {
    var r = rowObj_(data[i], i + 2);
    var st = r.post_status.toLowerCase();
    if (!r.story_id || !r.slides_spec || !r.images) continue;
    if (st !== 'queued' && st !== 'partly posted' && st !== 'posted') continue;
    if (r.review.toLowerCase() === 'hold') continue;
    if (allDone_(r)) continue;
    out.push(r);
  }
  return out;
}

function carouselOff_(r) {
  try { return JSON.parse(r.slides_spec).carousel === false; } catch (e) { return false; }
}

// ------------------------------------------------------------------ tokens
function token_(page) {
  var t = props_().getProperty('IG_TOKEN_' + String(page).toUpperCase());
  if (!t) throw new Error('No Instagram token saved for ' + page);
  return t;
}
/** Runs weekly (trigger made by setup): keeps the 60-day Instagram token alive. */
function refreshTokens() {
  ['TRICHY'].forEach(function (p) {
    var key = 'IG_TOKEN_' + p, t = props_().getProperty(key);
    if (!t) return;
    var res = UrlFetchApp.fetch('https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=' +
      encodeURIComponent(t), { muteHttpExceptions: true });
    var d = JSON.parse(res.getContentText());
    if (d.access_token) {
      props_().setProperty(key, d.access_token);
    } else {
      GmailApp.sendEmail(OWNER_EMAIL, '[TRICHY360] Instagram token refresh failed – ' + p,
        'The Instagram token for ' + p + ' could not be refreshed:\n' + res.getContentText() +
        '\n\nPlease generate a new token in the Meta developer app and save it in Apps Script → Project Settings → Script properties (' + key + ').');
    }
  });
}

// ------------------------------------------------------------------ recorded voice
function voiceFolder_() {
  var id = props_().getProperty('VOICE_FOLDER_ID');
  if (id) return DriveApp.getFolderById(id);
  var f = DriveApp.getFolderById(ROOT_FOLDER_ID).createFolder('Voice');
  props_().setProperty('VOICE_FOLDER_ID', f.getId());
  return f;
}
function voice_(story) {
  var it = voiceFolder_().getFiles();
  while (it.hasNext()) {
    var f = it.next(), name = f.getName();
    if (name.toLowerCase().indexOf(String(story).toLowerCase() + '.') === 0 && f.getSize() < 15 * 1024 * 1024) {
      var ext = name.substring(name.lastIndexOf('.'));
      return { ok: true, found: true, name: name, ext: ext, data: Utilities.base64Encode(f.getBlob().getBytes()) };
    }
  }
  return { ok: true, found: false };
}

// ------------------------------------------------------------------ after posting
function hashtags_(caption) {
  return (String(caption).match(/#[^\s#]+/g) || []).join(' ');
}
function posted_(b) {
  var sh = sheet_();
  var vals = sh.getRange(b.row, 1, 1, NCOLS).getValues()[0];
  var r = rowObj_(vals, b.row);
  var label = PAGE_LABEL[b.page] || b.page;
  var kindLabel = b.kind === 'reel' ? 'Reel' : 'Carousel';
  var time = nowIst_();

  if (b.dry_run) {
    appendNote_(sh, b.row, r.notes, time + ' TEST ' + kindLabel + ' ' + label + ' (not posted): ' + (b.media_urls || []).join(' '));
    GmailApp.sendEmail(OWNER_EMAIL, '[TRICHY360 TEST – NOT POSTED] ' + label + ' ' + kindLabel + ' – ' + r.headline_ta,
      emailBody_(r, b, label, kindLabel, time, true));
    return { ok: true };
  }

  if (b.kind === 'reel') {
    var prev = r.reel_link ? r.reel_link + '\n' : '';
    sh.getRange(b.row, C.reel_link).setValue(prev + label + ': ' + b.permalink);
    r.reel_link = prev + label + ': ' + b.permalink;
    sh.getRange(b.row, C.post_status).setValue(allDone_(r) ? 'Posted' : 'Partly posted');
  } else {
    sh.getRange(b.row, PAGE_COL[b.page]).setValue(b.permalink);
    r[b.page + '_link'] = b.permalink;
    sh.getRange(b.row, C.post_status).setValue(allDone_(r) ? 'Posted' : 'Partly posted');
  }
  sh.getRange(b.row, C.posted_at).setValue("'" + time);
  appendNote_(sh, b.row, r.notes, time + ' ' + kindLabel + ' posted to ' + label);

  // Google Doc: add a "Posted" section
  if (r.doc) {
    try {
      var body = DocumentApp.openByUrl(r.doc).getBody();
      body.appendParagraph('Posted to Instagram – ' + label + ' (' + kindLabel + ')').setHeading(DocumentApp.ParagraphHeading.HEADING2);
      body.appendListItem('Posted at: ' + time + ' IST');
      body.appendListItem('Instagram link: ' + b.permalink);
      if (b.kind === 'carousel') body.appendListItem('Slides: ' + b.slides);
      if (b.voice) body.appendListItem('Voice: ' + b.voice);
      body.appendListItem('Hashtags: ' + hashtags_(b.caption));
      body.appendParagraph('Caption used:').setBold(true);
      body.appendParagraph(b.caption).setBold(false);
    } catch (err) {
      appendNote_(sh, b.row, sh.getRange(b.row, C.notes).getValue(), 'Doc update failed: ' + err);
    }
  }
  GmailApp.sendEmail(OWNER_EMAIL, '[TRICHY360 POSTED] ' + label + ' ' + kindLabel + ' – ' + r.headline_ta,
    emailBody_(r, b, label, kindLabel, time, false));
  props_().deleteProperty('ERR_' + b.row + '_' + b.page + '_' + b.kind);
  return { ok: true };
}

function emailBody_(r, b, label, kindLabel, time, test) {
  return [
    test ? 'TEST RUN – nothing was posted to Instagram.' : 'Posted to Instagram.',
    '',
    'Page: ' + label,
    'Type: ' + kindLabel + (b.kind === 'carousel' ? ' (' + b.slides + ' slides)' : ''),
    'Time: ' + time + ' IST',
    'Instagram link: ' + (b.permalink || '(test – not posted)'),
    b.voice ? 'Voice: ' + b.voice : '',
    b.checks ? 'Checks passed before posting: ' + b.checks : '',
    '',
    'Story ID: ' + r.story_id,
    'Headline: ' + r.headline_ta,
    'English: ' + r.headline_en,
    'Category: ' + r.category + ' | Location: ' + r.location + ' | Importance: ' + r.importance,
    'Source news link: ' + (r.source || '(not recorded)'),
    'Verification: ' + r.verification,
    '',
    'CAPTION USED:',
    b.caption,
    '',
    'HASHTAGS: ' + hashtags_(b.caption),
    '',
    'Images / video used: ' + (b.media_urls || []).join('\n'),
    '',
    'Sources (not shown on Instagram): ' + r.source + (r.other_sources ? '\n' + r.other_sources : ''),
    'Google Doc: ' + r.doc,
    'Sheet: ' + SHEET_LINK,
    'Notion: ' + r.notion
  ].filter(function (x) { return x !== null; }).join('\n');
}

function appendNote_(sh, row, oldNotes, text) {
  sh.getRange(row, C.notes).setValue((oldNotes ? oldNotes + '\n' : '') + text);
}

function error_(b) {
  var sh = sheet_();
  var r = rowObj_(sh.getRange(b.row, 1, 1, NCOLS).getValues()[0], b.row);
  var key = 'ERR_' + b.row + '_' + b.page + '_' + b.kind;
  var n = Number(props_().getProperty(key) || 0) + 1;
  props_().setProperty(key, String(n));
  appendNote_(sh, b.row, r.notes, nowIst_() + ' ERROR ' + b.kind + ' ' + b.page + ' (try ' + n + '): ' + b.error);
  if (n >= 3) {
    sh.getRange(b.row, C.review).setValue('Hold');
    GmailApp.sendEmail(OWNER_EMAIL, '[TRICHY360 PROBLEM] Could not post ' + r.story_id + ' – ' + r.headline_ta,
      'Posting failed 3 times, so this story is now on Hold.\n\nPage: ' + (PAGE_LABEL[b.page] || b.page) + '\nType: ' + b.kind +
      '\nError: ' + b.error + '\n\nSheet: ' + SHEET_LINK + ' (row ' + b.row + ')\nTo try again, clear "Hold" in the Review status column.');
  }
  return { ok: true };
}

// ------------------------------------------------------------------ reading your image reply
/**
 * Runs every 5 minutes. Looks for your reply to a "[TRICHY360 IMAGES NEEDED]" email, takes the attached images
 * (a zip, or the images themselves), uploads them to Cloudinary, saves the links in the Sheet and queues the story.
 * Skip a story by writing  SKIP RN-26  in your reply (e.g. when you already posted it yourself).
 */
function processReplies() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) return;
  try {
    expireOld_();
    var p = props_();
    var done = JSON.parse(p.getProperty('DONE_MSGS') || '[]');
    var allowed = allowedSenders_();
    try { processManual_(p, done, allowed); } catch (err0) {
      GmailApp.sendEmail(OWNER_EMAIL, '[TRICHY360 PROBLEM] Manual story intake failed', String(err0));
    }
    try { processReadyReels_(p, allowed); } catch (err1) {
      GmailApp.sendEmail(OWNER_EMAIL, '[TRICHY360 PROBLEM] Ready-reel intake failed', String(err1));
    }
    done = JSON.parse(p.getProperty('DONE_MSGS') || '[]');
    var threads = GmailApp.search('subject:"TRICHY360 IMAGES" newer_than:5d', 0, 30);
    threads.forEach(function (th) {
      var m = th.getFirstMessageSubject().match(/B\d{8}-\d{4}/);
      if (!m) return;
      th.getMessages().forEach(function (msg) {
        var id = msg.getId();
        if (done.indexOf(id) >= 0) return;
        var from = String(msg.getFrom()).replace(/^.*<|>.*$/g, '').trim().toLowerCase();
        if (allowed.indexOf(from) < 0) return;
        done.push(id);
        p.setProperty('DONE_MSGS', JSON.stringify(done.slice(-200)));
        try { handleReply_(msg, m[0]); } catch (err) {
          GmailApp.sendEmail(OWNER_EMAIL, '[TRICHY360 PROBLEM] Could not read your image reply', String(err) + '\n\nBatch ' + m[0]);
        }
      });
    });
  } finally {
    lock.releaseLock();
  }
}

// ------------------------------------------------------------------ MANUAL STORIES (written elsewhere, e.g. with another Claude account, sent by e-mail)
// E-mail subject must contain  TRICHY360 STORY . Body (or a .json/.txt attachment) = the story JSON, attachments = the images (png/jpg/zip).
// One story per e-mail: all images belong to it. Several stories in one e-mail ({"stories":[...]}): name the images S1_1.png, S1_2.png, S2_1.png ...
// The story is checked, duplicates are refused, the images are uploaded and the story is QUEUED: posting (with the Instagram duplicate check and the fact gate) is automatic.
var MANUAL_LAST = 'மேலும் செய்திகளுக்கு கோயம்புத்தூர் த்ரீ சிக்ஸ்டி பக்கத்தை பின்தொடருங்கள்.';
var MANUAL_FOLLOW = 'கோயம்புத்தூர் செய்திகளைத் தவறவிடாமல் இருக்க Save செய்து Follow செய்யுங்கள் 📌';

function stripTags_(t) { return String(t || '').replace(/<[^>]+>/g, ''); }

function tokens_(t) {
  var out = {};
  String(t || '').toLowerCase().replace(/[^஀-௿a-z0-9 ]/g, ' ').split(/\s+/).forEach(function (w) { if (w.length >= 3) out[w.slice(0, 5)] = 1; });
  return out;
}
function overlap_(a, b) {
  var ta = tokens_(a), tb = tokens_(b), n = 0, na = Object.keys(ta).length, nb = Object.keys(tb).length;
  Object.keys(ta).forEach(function (k) { if (tb[k]) n++; });
  return (na && nb) ? n / Math.min(na, nb) : 0;
}

function manualProblems_(st, recent) {
  var p = [];
  ['tamil_headline', 'english_headline', 'category', 'location', 'importance', 'post_to', 'slides_spec', 'reel_script', 'caption'].forEach(function (k) {
    if (!st[k]) p.push('missing field: ' + k);
  });
  if (p.length) return p;
  var sp = typeof st.slides_spec === 'string' ? JSON.parse(st.slides_spec) : st.slides_spec;
  st.slides_spec = sp;
  var sl = sp.slides || [];
  if (sp.v !== 3) p.push('slides_spec.v must be 3');
  if (sl.length < 3 || sl.length > 4) p.push('slides must be 3 or 4');
  if (String(sp.hl1 || '').length > 40) p.push('hl1 longer than 40 characters');
  if (String(sp.hl2 || '').length > 28) p.push('hl2 longer than 28 characters');
  sl.forEach(function (s, i) {
    if (stripTags_(s.title).length > 18) p.push('slide ' + (i + 1) + ' title longer than 18 characters');
    var ln = s.lines || [];
    if (ln.length < 2 || ln.length > 3) p.push('slide ' + (i + 1) + ' must have 2-3 lines');
    ln.forEach(function (l, j) { if (stripTags_(l).length > 60) p.push('slide ' + (i + 1) + ' line ' + (j + 1) + ' longer than 60 characters'); });
  });
  if (['High', 'Medium', 'Low'].indexOf(st.importance) < 0) p.push('importance must be High, Medium or Low');
  if (!/^Coimbatore 360\s*$/.test(st.post_to)) p.push("post_to must be 'Coimbatore 360' (the only page; Coimbatore-district news only)");
  var rs = String(st.reel_script).trim();
  if (rs.indexOf(MANUAL_LAST) < 0) rs = rs.replace(/\s+$/, '') + ' ' + MANUAL_LAST;   // fixed closing line is added if missing
  st.reel_script = rs;
  if (/[0-9A-Za-z]/.test(rs.replace(MANUAL_LAST, ''))) p.push('reel_script must have no digits or English letters (write numbers in Tamil words)');
  var wc = rs.split(/\s+/).length;
  if (wc < 85 || wc > 120) p.push('reel_script has ' + wc + ' words, need 85-120 (detailed reel)');
  var cap = String(st.caption);
  if (cap.indexOf(MANUAL_FOLLOW) < 0) cap = cap.replace(/\s+$/, '') + '\n\n' + MANUAL_FOLLOW;
  st.caption = cap;
  var tags = cap.match(/#\S+/g) || [];
  if (tags.length < 3 || tags.length > 5) p.push('caption needs 3-5 hashtags, has ' + tags.length);
  if (/தினமலர்|தினத்தந்தி|தினமணி|மாலைமலர்|தினகரன்|இந்து தமிழ்|ஆதாரம்|source:|https?:|www\./i.test(JSON.stringify(st).replace(/"source":"[^"]*"/, ''))) p.push('an outlet name or link appears in the text (remove it; put the link only in the "source" field)');
  // duplicate: same news already in the Sheet (any status) or posted earlier
  recent.forEach(function (r) {
    if (overlap_(st.tamil_headline, r.headline_ta) >= 0.65 || (st.source && r.source && String(st.source).trim() === String(r.source).trim())) {
      p.push('DUPLICATE of ' + r.story_id + ' (' + r.post_status + '): ' + r.headline_ta);
    }
  });
  return p;
}

function jsonFromText_(t) {
  t = String(t || '').replace(/```(json)?/gi, '');
  var a = t.search(/[\[{]/);
  if (a < 0) throw new Error('no JSON found in the e-mail');
  var open = t.charAt(a), close = open === '{' ? '}' : ']';
  var b = t.lastIndexOf(close);
  return JSON.parse(t.slice(a, b + 1));
}

function processManual_(p, done, allowed) {
  var threads = GmailApp.search('subject:"TRICHY360 STORY" newer_than:3d', 0, 20);
  threads.forEach(function (th) {
    th.getMessages().forEach(function (msg) {
      var id = msg.getId();
      if (done.indexOf(id) >= 0) return;
      var from = String(msg.getFrom()).replace(/^.*<|>.*$/g, '').trim().toLowerCase();
      if (allowed.indexOf(from) < 0) return;
      if (!/TRICHY360 STORY/i.test(msg.getSubject())) return;
      done.push(id);
      p.setProperty('DONE_MSGS', JSON.stringify(done.slice(-200)));
      var report = [];
      try { report = manualOne_(msg); } catch (err) { report = ['Could not read the e-mail: ' + err]; }
      GmailApp.sendEmail(OWNER_EMAIL, '[TRICHY360 STORY RECEIVED] ' + msg.getSubject().replace(/^(re|fwd?):\s*/i, ''),
        report.join('\n') + '\n\nSheet: ' + SHEET_LINK);
    });
  });
}

function manualOne_(msg) {
  var sh = sheet_(), report = [];
  // JSON: body first, else a .json/.txt attachment
  var data;
  var body = String(msg.getPlainBody()).replace(/\r/g, '');
  try { data = jsonFromText_(body); } catch (e1) {
    var found = null;
    msg.getAttachments({ includeInlineImages: false, includeAttachments: true }).forEach(function (a) {
      if (!found && /\.(json|txt)$/i.test(a.getName())) { try { found = jsonFromText_(a.getDataAsString('UTF-8')); } catch (e2) { } }
    });
    if (!found) throw new Error('the story JSON was not found or is not valid JSON (' + e1 + ')');
    data = found;
  }
  var stories = Array.isArray(data) ? data : (data.stories || [data]);
  var blobs = imageBlobs_(msg).concat(driveBlobs_(msg, report));
  blobs.sort(function (a, b) { return naturalKey_(a.getName()) < naturalKey_(b.getName()) ? -1 : 1; });
  var recent = recent_();
  var no = nextStoryNo_(sh), rows = [];
  stories.forEach(function (st, idx) {
    var label = 'Story ' + (idx + 1) + ' (' + String(st.tamil_headline || '').slice(0, 40) + ')';
    var probs;
    try { probs = manualProblems_(st, recent); } catch (e3) { probs = ['unreadable story: ' + e3]; }
    var mine;
    if (stories.length === 1) mine = blobs.slice();
    else mine = blobs.filter(function (b) { var m = String(b.getName()).match(/(?:^|[^A-Za-z])S(\d+)[_\-. ]/i); return m && +m[1] === idx + 1; });
    mine = mine.slice(0, 10);
    if (mine.length < MIN_IMAGES) probs.push('only ' + mine.length + ' image(s) found, at least ' + MIN_IMAGES + ' needed (ONE clear picture of the news is enough)');
    if (probs.length) { report.push('NOT ADDED - ' + label + ':\n  - ' + probs.join('\n  - ')); return; }
    no++;
    var id = 'RN-' + no;
    var urls = mine.map(function (b) { return uploadImage_(b, id); });
    var row = new Array(NCOLS).fill('');
    row[C.story_id - 1] = id;
    row[C.researched - 1] = "'" + nowIst_();
    row[C.published - 1] = "'" + (st.published || nowIst_());
    row[C.headline_ta - 1] = st.tamil_headline; row[C.headline_en - 1] = st.english_headline;
    row[C.category - 1] = st.category; row[C.location - 1] = st.location; row[C.importance - 1] = st.importance;
    row[C.verification - 1] = st.verification || 'MANUAL - written by the owner/friend, checked by the fact gate before posting';
    row[C.source - 1] = st.source || '';
    row[C.caption - 1] = st.caption; row[C.email_sent - 1] = 'Manual';
    row[C.review - 1] = 'Auto'; row[C.post_to - 1] = st.post_to; row[C.reel - 1] = 'Yes';
    row[C.reel_script - 1] = st.reel_script;
    row[C.slides_spec - 1] = JSON.stringify(st.slides_spec);
    row[C.post_status - 1] = 'Queued';
    row[C.notes - 1] = nowIst_() + ' manual story by e-mail, ' + urls.length + ' images received';
    row[C.batch - 1] = 'MANUAL-' + Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyyMMdd-HHmm');
    row[C.prompts - 1] = urls.map(function (u, k) { return '(manual image ' + (k + 1) + ')'; }).join('\n---\n');
    row[C.images - 1] = JSON.stringify(urls);
    rows.push(row);
    recent.push({ story_id: id, headline_ta: st.tamil_headline, source: st.source || '', post_status: 'Queued' });
    report.push('ADDED ' + id + ' - ' + label + ': ' + urls.length + ' images. The reel will be made and posted automatically in about 20-40 minutes (Instagram duplicate check and fact check run first).');
  });
  if (rows.length) sh.getRange(sh.getLastRow() + 1, 1, rows.length, NCOLS).setValues(rows);
  return report;
}

// ------------------------------------------------------------------ READY REEL (video + caption already made, sent by e-mail)
// Subject contains  TRICHY360 REEL . Attach ONE zip (or the files directly) holding ONE .md/.txt (the caption) and ONE video (.mp4/.mov).
// A PAGE: line at the top of the .md is accepted but ignored (there is one page: coimbatore). Nothing is rebuilt: the video is posted as it is,
// with the caption (standard hashtag/AI-line rules), but ONLY if the same news is not already on the Instagram page (checked right before posting).
function allFiles_(msg, report) {
  var out = [];
  function add(b) {
    var bn = String(b.getName());
    if (/(^|\/)\.|__MACOSX/.test(bn)) return;
    out.push(b);
  }
  msg.getAttachments({ includeInlineImages: false, includeAttachments: true }).forEach(function (a) {
    var n = String(a.getName()).toLowerCase();
    if (n.slice(-4) === '.zip' || String(a.getContentType()).indexOf('zip') >= 0) Utilities.unzip(a).forEach(add); else add(a);
  });
  var html = String(msg.getBody()), q = html.search(/class="gmail_quote/);
  var typed = q >= 0 ? html.slice(0, q) : html, ids = [], m, re = /drive\.google\.com\/file\/d\/([\w-]+)/g;
  while ((m = re.exec(typed))) if (ids.indexOf(m[1]) < 0) ids.push(m[1]);
  ids.forEach(function (id) {
    try {
      var b = DriveApp.getFileById(id).getBlob(), n = String(b.getName()).toLowerCase();
      if (n.slice(-4) === '.zip' || String(b.getContentType()).indexOf('zip') >= 0) Utilities.unzip(b).forEach(add); else add(b);
    } catch (err) { report.push('Could not read the Drive file ' + id + ': ' + err); }
  });
  return out;
}

function uploadVideo_(blob, story) {
  var res = UrlFetchApp.fetch('https://api.cloudinary.com/v1_1/' + CLOUD_NAME + '/video/upload', {
    method: 'post', muteHttpExceptions: true,
    payload: { file: blob, upload_preset: UPLOAD_PRESET, folder: 'coimbatore360/ready/' + story, resource_type: 'video' }
  });
  var d = JSON.parse(res.getContentText());
  if (!d.secure_url) throw new Error('Video upload failed for ' + story + ': ' + res.getContentText().slice(0, 300));
  return d.secure_url;
}

function processReadyReels_(p, allowed) {
  var done = JSON.parse(p.getProperty('DONE_MSGS') || '[]');
  GmailApp.search('subject:"TRICHY360 REEL" -subject:RECEIVED -subject:POSTED newer_than:3d', 0, 20).forEach(function (th) {
    th.getMessages().forEach(function (msg) {
      var id = msg.getId();
      if (done.indexOf(id) >= 0) return;
      // our own status e-mails ([TRICHY360 REEL RECEIVED], [TRICHY360 POSTED] ...) also contain "TRICHY360 REEL": never read them as reels (that made a loop)
      if (/RECEIVED|POSTED|NEEDED|NOT ADDED|\[TRICHY360/i.test(msg.getSubject())) return;
      var from = String(msg.getFrom()).replace(/^.*<|>.*$/g, '').trim().toLowerCase();
      if (allowed.indexOf(from) < 0 || !/TRICHY360 REEL/i.test(msg.getSubject())) return;
      done.push(id);
      p.setProperty('DONE_MSGS', JSON.stringify(done.slice(-200)));
      var report = [];
      try { report = readyOne_(msg); } catch (err) { report = ['Could not process the e-mail: ' + err]; }
      GmailApp.sendEmail(OWNER_EMAIL, '[TRICHY360 REEL RECEIVED] ' + msg.getSubject().replace(/^(re|fwd?):\s*/i, ''),
        report.join('\n') + '\n\nSheet: ' + SHEET_LINK);
    });
  });
}

// One e-mail may hold ONE OR MORE zip files. Each zip = ONE reel (its own .md caption + ONE video).
// Loose .md/.mp4 files attached directly (not in a zip) are treated as one reel together.
function readyGroups_(msg, report) {
  var groups = [], loose = [];
  function isZip(b) { return String(b.getName()).toLowerCase().slice(-4) === '.zip' || String(b.getContentType()).indexOf('zip') >= 0; }
  function clean(list) { return list.filter(function (b) { return !/(^|\/)\.|__MACOSX/.test(String(b.getName())); }); }
  function take(b) {
    if (isZip(b)) groups.push({ name: String(b.getName()), files: clean(Utilities.unzip(b)) });
    else loose.push(b);
  }
  msg.getAttachments({ includeInlineImages: false, includeAttachments: true }).forEach(take);
  var html = String(msg.getBody()), q = html.search(/class="gmail_quote/);
  var typed = q >= 0 ? html.slice(0, q) : html, ids = [], m, re = /drive\.google\.com\/file\/d\/([\w-]+)/g;
  while ((m = re.exec(typed))) if (ids.indexOf(m[1]) < 0) ids.push(m[1]);
  ids.forEach(function (id) {
    try { take(DriveApp.getFileById(id).getBlob()); }
    catch (err) { report.push('Could not read the Drive file ' + id + ': ' + err); }
  });
  if (loose.length) groups.push({ name: 'loose files', files: loose });
  return groups;
}

function readyOne_(msg) {
  var report = [];
  var groups = readyGroups_(msg, report);
  if (!groups.length) return report.concat(['NOT ADDED: no zip file (or caption/video file) found in this e-mail. Attach each reel as a zip.']);
  groups.forEach(function (g) {
    try { addReel_(g, report); }
    catch (err) { report.push('NOT ADDED ' + g.name + ': ' + err); }
  });
  return report;
}

// one zip = one caption (.md) + one or more videos. Each video becomes its own reel row.
// Coimbatore: every video goes to the one page (coimbatore), whatever its file name or PAGE line says.
function pageFromName_(name) {
  return 'coimbatore';
}

function addReel_(g, report) {
  var files = g.files;
  var txt = files.filter(function (b) { return /\.(md|txt|markdown)$/i.test(b.getName()); });
  var vids = files.filter(function (b) { return /\.(mp4|mov|m4v)$/i.test(b.getName()); });
  if (txt.length !== 1) { report.push('NOT ADDED ' + g.name + ': needs exactly ONE .md caption file inside, found ' + txt.length); return; }
  if (!vids.length) { report.push('NOT ADDED ' + g.name + ': needs at least ONE video (.mp4) inside, found 0'); return; }
  var lines = txt[0].getDataAsString('UTF-8').replace(/^﻿/, '').replace(/\r/g, '').split('\n');
  var defPage = 'coimbatore';
  while (lines.length && /^\s*(page|post_to)\s*:/i.test(lines[0])) lines.shift();   // settings line: one page only, nothing to choose
  var cap = lines.map(function (l) { return l.replace(/^\s*#{1,6}\s+(?=\S)/, '').replace(/\*\*|__/g, ''); }).join('\n').trim();
  if (!cap) { report.push('NOT ADDED ' + g.name + ': the .md caption file is empty'); return; }
  var head = (cap.split('\n').filter(function (l) { return l.trim(); })[0] || '').trim();
  vids.forEach(function (vb) {
    var pg = pageFromName_(vb.getName()) || defPage;
    try { addRow_(vb, pg, cap, head, g.name, report); }
    catch (err) { report.push('NOT ADDED ' + vb.getName() + ': ' + err); }
  });
}

function addRow_(vid, page, cap, head, groupName, report) {
  var sh = sheet_();
  // owner-verified reels: no duplicate check here (owner decision, 24 Oct) - posted as received
  var no = nextStoryNo_(sh) + 1, id = 'RN-' + no;
  var url = uploadVideo_(vid, id);
  var row = new Array(NCOLS).fill('');
  var to = 'Coimbatore 360';      // one page only
  row[C.story_id - 1] = id;
  row[C.researched - 1] = "'" + nowIst_(); row[C.published - 1] = "'" + nowIst_();
  row[C.headline_ta - 1] = head; row[C.headline_en - 1] = '';
  row[C.category - 1] = 'Ready reel'; row[C.location - 1] = ''; row[C.importance - 1] = 'Medium';
  row[C.verification - 1] = 'READY REEL - made and approved by the owner';
  row[C.caption - 1] = cap; row[C.email_sent - 1] = 'Manual';
  row[C.review - 1] = 'Auto'; row[C.post_to - 1] = to; row[C.reel - 1] = 'Yes';
  row[C.slides_spec - 1] = JSON.stringify({ v: 3, ready_reel: true, carousel: false });
  row[C.post_status - 1] = 'Queued';
  row[C.notes - 1] = nowIst_() + ' ready reel by e-mail (' + groupName + ', ' + vid.getName() + ', video ' + Math.round(vid.getBytes().length / 1048576 * 10) / 10 + ' MB)';
  row[C.batch - 1] = 'READY-' + Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyyMMdd-HHmm');
  row[C.images - 1] = JSON.stringify([url]);
  sh.getRange(sh.getLastRow() + 1, 1, 1, NCOLS).setValues([row]);
  report.push('ADDED ' + id + ' (' + vid.getName() + ') for ' + to + ': "' + head.slice(0, 60) + '". Posted automatically within about 20-40 minutes unless the same news is already on that Instagram page.');
}


// ------------------------------------------------------------------ AUTOMATIC IMAGES (free AI models, made by the posting job)
function autoPending_() {
  var sh = sheet_(), last = sh.getLastRow();
  if (last < 2) return [];
  var out = [];
  sh.getRange(2, 1, last - 1, NCOLS).getValues().forEach(function (v, i) {
    var r = rowObj_(v, i + 2);
    if (r.post_status === 'Auto images' && r.prompts) {
      out.push({ row: r.row, story_id: r.story_id, source: r.source, prompts: String(r.prompts), category: r.category, location: r.location, post_to: r.post_to, headline_ta: r.headline_ta, headline_en: r.headline_en, researched: r.researched });
    }
  });
  return out;
}

function setImages_(b) {
  var sh = sheet_();
  var r = sh.getRange(b.row, 1).getValue();
  if (String(r) !== String(b.story_id)) return { ok: false, error: 'row does not match ' + b.story_id };
  var cur = sh.getRange(b.row, C.post_status).getValue();
  if (cur !== 'Auto images') return { ok: true, skipped: 'status is ' + cur };
  sh.getRange(b.row, C.images).setValue(JSON.stringify(b.images || []));
  sh.getRange(b.row, C.post_status).setValue('Queued');
  var note = nowIst_() + ' automatic images (free AI models) received: ' + (b.images || []).length;
  sh.getRange(b.row, C.notes).setValue(String(sh.getRange(b.row, C.notes).getValue() || '') + ' | ' + note);
  return { ok: true, queued: true };
}

function allowedSenders_() {
  var extra = String(props_().getProperty('ALLOWED_SENDERS') || '').split(',');
  return [OWNER_EMAIL.toLowerCase()].concat(extra.map(function (x) { return x.trim().toLowerCase(); }).filter(String));
}

function imageBlobs_(msg) {
  var out = [];
  msg.getAttachments({ includeInlineImages: false, includeAttachments: true }).forEach(function (a) {
    var n = String(a.getName()).toLowerCase();
    var blobs = (n.slice(-4) === '.zip' || a.getContentType().indexOf('zip') >= 0) ? Utilities.unzip(a) : [a];
    blobs.forEach(function (b) {
      var bn = String(b.getName());
      if (/(^|\/)\.|__MACOSX/.test(bn)) return;
      if (/\.(png|jpe?g|webp)$/i.test(bn)) out.push(b);
    });
  });
  return out;
}

/** Gmail turns a big attachment (over 25 MB) into a Google Drive link instead of an attachment. Read zip/image files linked in what you typed (not in the quoted original). */
function driveBlobs_(msg, report) {
  var html = String(msg.getBody());
  var q = html.search(/class="gmail_quote/);
  var typed = q >= 0 ? html.slice(0, q) : html;
  var ids = [], m, re = /drive\.google\.com\/file\/d\/([\w-]+)/g;
  while ((m = re.exec(typed))) if (ids.indexOf(m[1]) < 0) ids.push(m[1]);
  var out = [];
  ids.forEach(function (id) {
    try {
      var f = DriveApp.getFileById(id);
      var n = String(f.getName()).toLowerCase();
      var b = f.getBlob();
      var list = (n.slice(-4) === '.zip' || String(b.getContentType()).indexOf('zip') >= 0) ? Utilities.unzip(b) : [b];
      list.forEach(function (x) {
        var bn = String(x.getName());
        if (/(^|\/)\.|__MACOSX/.test(bn)) return;
        if (/\.(png|jpe?g|webp)$/i.test(bn)) out.push(x);
      });
    } catch (err) {
      report.push('Could not read the Drive file ' + id + ': ' + err + ' (if it is very large, send the images as 2-3 smaller zips, up to 40 MB each)');
    }
  });
  return out;
}

/** Run once from the editor if a reply was read before this fix: lets processReplies read the recent replies again. */
function reprocessRecent() {
  props_().deleteProperty('DONE_MSGS');
  processReplies();
}

function naturalKey_(name) {
  return String(name).replace(/\d+/g, function (d) { return ('00000000' + d).slice(-8); }).toLowerCase();
}

function handleReply_(msg, batchId) {
  var sh = sheet_();
  var last = sh.getLastRow();
  if (last < 2) return;
  var data = sh.getRange(2, 1, last - 1, NCOLS).getValues();
  var rows = [];
  for (var i = 0; i < data.length; i++) {
    var r = rowObj_(data[i], i + 2);
    if (r.batch === batchId && (r.post_status === 'Awaiting images' || r.post_status === 'Auto images') && r.review.toLowerCase() !== 'hold') rows.push(r);
  }
  var report = [];

  // SKIP lines (only in what you typed, not in the quoted original)
  var body = String(msg.getPlainBody()).replace(/\r/g, '');
  var storyM = String(msg.getSubject() || '').match(/RN-\d+/);
  if (storyM) rows = rows.filter(function (r) { return r.story_id === storyM[0]; });
  // cut everything from the quoted original ("On <date> ... wrote:" which may wrap over two lines, "> " lines, "Original Message")
  var cut = body.search(/(^|\n)[ \t]*On [^\n]*(\n[^\n]*)?wrote:|(^|\n)[ \t]*>|(^|\n)[ \t]*-{2,}[ \t]*Original|(^|\n)[ \t]*From:/i);
  var typed = cut >= 0 ? body.slice(0, cut) : body;
  var skipped = {};
  // only a line that STARTS with SKIP counts (so example text can never trigger it)
  (typed.match(/^[ \t]*SKIP[ \t]+RN-?\d+/gmi) || []).forEach(function (x) {
    skipped['RN-' + x.match(/\d+/)[0]] = true;
  });
  rows = rows.filter(function (r) {
    if (skipped[r.story_id]) {
      sh.getRange(r.row, C.review).setValue('Hold');
      sh.getRange(r.row, C.post_status).setValue('Skipped (posted manually)');
      report.push(r.story_id + ': skipped as you asked');
      return false;
    }
    return true;
  });

  var blobs = imageBlobs_(msg).concat(driveBlobs_(msg, report));
  var noImg = /(not needed|without image|no image|no images|don'?t need images?)/i.test(typed);
  if (noImg && !blobs.length && rows.length) {
    rows.forEach(function (r) {
      sh.getRange(r.row, C.images).setValue('["NOIMAGE"]');
      sh.getRange(r.row, C.post_status).setValue('Queued');
      appendNote_(sh, r.row, r.notes, nowIst_() + ' owner: no images - the reel is made without pictures (plain background)');
      report.push(r.story_id + ': no images - the reel will be made without pictures and posted automatically');
    });
    rows = [];
  }
  if (blobs.length && rows.length) {
    var byStory = {};
    var unnamed = [];
    blobs.forEach(function (b) {
      var nm = String(b.getName());
      var sm = nm.match(/RN-?(\d+)/i);
      if (sm) {
        var key = 'RN-' + sm[1];
        (byStory[key] = byStory[key] || []).push(b);
      } else unnamed.push(b);
    });
    unnamed.sort(function (a, b) { return naturalKey_(a.getName()) < naturalKey_(b.getName()) ? -1 : 1; });
    rows.forEach(function (r) {
      var need = promptCount_(r);
      var mine = (byStory[r.story_id] || []).sort(function (a, b) { return naturalKey_(a.getName()) < naturalKey_(b.getName()) ? -1 : 1; });
      while (mine.length < need && unnamed.length) mine.push(unnamed.shift());
      mine = mine.slice(0, 10);
      if (mine.length < Math.min(MIN_IMAGES, need)) {
        if (mine.length) report.push(r.story_id + ': only ' + mine.length + ' image(s) found, need ' + need + ' – please reply again with all ' + need + ' images');
        else report.push(r.story_id + ': no images found yet');
        return;
      }
      var urls = mine.map(function (b) { return uploadImage_(b, r.story_id); });
      sh.getRange(r.row, C.images).setValue(JSON.stringify(urls));
      sh.getRange(r.row, C.post_status).setValue('Queued');
      appendNote_(sh, r.row, r.notes, nowIst_() + ' ' + urls.length + ' images received (batch ' + batchId + ')');
      report.push(r.story_id + ': ' + urls.length + ' images received – the reel will be made and posted within about 20-40 minutes');
    });
  } else if (!report.length && rows.length) {
    return; // e.g. the original email itself: nothing to do
  }
  if (report.length) {
    GmailApp.sendEmail(OWNER_EMAIL, '[TRICHY360 IMAGES RECEIVED] ' + batchId,
      report.join('\n') + '\n\nSheet: ' + SHEET_LINK);
  }
}

function promptCount_(r) {
  var n = String(r.prompts || '').split(/\n-{3,}\n/).filter(function (x) { return x.trim(); }).length;
  return n || 5;
}

function uploadImage_(blob, story) {
  var res = UrlFetchApp.fetch('https://api.cloudinary.com/v1_1/' + CLOUD_NAME + '/image/upload', {
    method: 'post', muteHttpExceptions: true,
    payload: { file: blob, upload_preset: UPLOAD_PRESET, folder: 'coimbatore360/src/' + story }
  });
  var d = JSON.parse(res.getContentText());
  if (!d.secure_url) throw new Error('Image upload failed for ' + story + ': ' + res.getContentText().slice(0, 300));
  return d.secure_url;
}

/** Stories still waiting for images after EXPIRE_HOURS are closed, so old news is never posted. */
function expireOld_() {
  var sh = sheet_();
  var last = sh.getLastRow();
  if (last < 2) return;
  var data = sh.getRange(2, 1, last - 1, NCOLS).getValues();
  for (var i = 0; i < data.length; i++) {
    var r = rowObj_(data[i], i + 2);
    if (r.post_status !== 'Awaiting images') continue;
    var t = parseIst_(r.researched);
    if (t && (Date.now() - t.getTime()) / 3600000 > EXPIRE_HOURS) {
      // no images from the owner in time: the free AI image models make them now (the posting job does it)
      sh.getRange(r.row, C.post_status).setValue('Auto images');
      appendNote_(sh, r.row, r.notes, nowIst_() + ' no reply within ' + EXPIRE_HOURS + ' hours - free AI images are tried, otherwise the reel is made without pictures');
    }
  }
}
function parseIst_(txt) {
  var m = String(txt).replace(/^'/, '').match(/(\d{1,2}) (\w{3}) (\d{4}),? (\d{1,2}):(\d{2})/);
  if (!m) return null;
  var mon = { Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5, Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11 }[m[2]];
  if (mon === undefined) return null;
  return new Date(Date.UTC(+m[3], mon, +m[1], +m[4], +m[5]) - 5.5 * 3600000);
}

// ------------------------------------------------------------------ one-time setup
/** Run once from the editor (and again after every update): secret key, Voice folder, triggers. Asks for Gmail permission. */
function setup() {
  var p = props_();
  if (!p.getProperty('BRIDGE_KEY')) p.setProperty('BRIDGE_KEY', Utilities.getUuid().replace(/-/g, ''));
  voiceFolder_();
  ScriptApp.getProjectTriggers().forEach(function (t) {
    var h = t.getHandlerFunction();
    if (h === 'refreshTokens' || h === 'processReplies') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('refreshTokens').timeBased().everyWeeks(1).onWeekDay(ScriptApp.WeekDay.SUNDAY).atHour(3).create();
  ScriptApp.newTrigger('processReplies').timeBased().everyMinutes(5).create();
  GmailApp.getInboxThreads(0, 1); // makes Google ask for Gmail permission now
  Logger.log('BRIDGE_KEY is saved in Script properties (not shown here).');
  Logger.log('Voice folder: https://drive.google.com/drive/folders/' + p.getProperty('VOICE_FOLDER_ID'));
}


// ------------------------------------------------------------------ free-model collector (GitHub Actions) -> Sheet + prompt file + email
/** last 150 rows (for duplicate detection by the collector) */
function recent_() {
  var sh = sheet_();
  var last = sh.getLastRow();
  if (last < 2) return [];
  var from = Math.max(2, last - 149);
  var data = sh.getRange(from, 1, last - from + 1, NCOLS).getValues();
  return data.map(function (v, i) {
    var r = rowObj_(v, from + i);
    return { story_id: r.story_id, researched: r.researched, headline_ta: r.headline_ta, headline_en: r.headline_en, source: r.source, post_status: r.post_status, images: r.images, category: r.category, location: r.location, post_to: r.post_to };
  });
}

/** website backfill (read only): every story already posted on Instagram, with the text, pictures and links the website shows */
function postedRows_() {
  var sh = sheet_();
  var last = sh.getLastRow();
  if (last < 2) return [];
  var data = sh.getRange(2, 1, last - 1, NCOLS).getValues();
  var out = [];
  for (var i = 0; i < data.length; i++) {
    var r = rowObj_(data[i], i + 2);
    var st = r.post_status.toLowerCase();
    if (!r.story_id || (st.indexOf('posted') !== 0 && st.indexOf('partly') !== 0)) continue;
    out.push({ story_id: r.story_id, researched: r.researched, published: r.published, headline_ta: r.headline_ta, headline_en: r.headline_en,
               category: r.category, location: r.location, source: r.source, caption: r.caption, reel_script: r.reel_script,
               images: r.images, reel_link: r.reel_link, coimbatore_link: r.coimbatore_link, spare_link: r.spare_link });
  }
  return out;
}

function nextStoryNo_(sh) {
  var last = sh.getLastRow(), mx = 0;
  if (last >= 2) sh.getRange(2, 1, last - 1, 1).getValues().forEach(function (x) {
    var m = String(x[0]).match(/RN-(\d+)/); if (m) mx = Math.max(mx, +m[1]);
  });
  return mx;
}

/** body: {stories:[{tamil_headline,english_headline,category,location,importance,post_to,slides_spec,reel_script,caption,prompts,source,published,verification,note,post_time}]}
 *  Appends one row per story (status "Awaiting images"), writes ONE prompt file to Drive and sends ONE short email. */
// Every news item found (all outlets, all pages) goes into the tab "All News" so the owner can analyse it. One row per URL; status is updated.
function archiveNews_(b) {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sh = ss.getSheetByName('All News');
  var head = ['Collected (IST)', 'Outlets', 'Area', 'URL', 'Title', 'Published', 'Outlets count', 'Score', 'Status', 'Story headline'];
  if (!sh) { sh = ss.insertSheet('All News'); sh.appendRow(head); sh.setFrozenRows(1); }
  var last = sh.getLastRow(), idx = {};
  if (last > 1) sh.getRange(2, 4, last - 1, 1).getValues().forEach(function (r, i) { idx[r[0]] = i + 2; });
  var add = [], rows = b.rows || [];
  rows.forEach(function (r) {
    if (idx[r.url] === -1) return;      // the same link twice in one batch (28 Oct: 'starting row of the range is too small')
    if (idx[r.url]) {
      sh.getRange(idx[r.url], 7, 1, 4).setValues([[r.mentions, r.score, r.status, r.story || '']]);
    } else {
      add.push([nowIst_(), r.source, r.area, r.url, r.title, "'" + (r.published || ''), r.mentions, r.score, r.status, r.story || '']);
      idx[r.url] = -1;
    }
  });
  if (add.length) sh.getRange(sh.getLastRow() + 1, 1, add.length, head.length).setValues(add);
  return { ok: true, added: add.length, updated: rows.length - add.length };
}

function addStories_(b) {
  var sh = sheet_();
  var stories = b.stories || [];
  if (!stories.length) {
    if (b.no_news) {
      GmailApp.sendEmail(OWNER_EMAIL, '[TRICHY360] No new news this round - ' + nowIst_(),
        'The news check ran at ' + nowIst_() + ' IST and found nothing new to post.\n\n' + String(b.no_news) +
        '\n\nYou do not need to send any images now. The next check is in about 3 hours.\n\nSheet: ' + SHEET_LINK);
    }
    return { ok: true, added: 0 };
  }
  var no = nextStoryNo_(sh);
  var now = new Date();
  var batch = 'B' + Utilities.formatDate(now, 'Asia/Kolkata', 'yyyyMMdd-HHmm');
  var rows = [], items = [], auto = 0;
  stories.forEach(function (st) {
    no++;
    var id = 'RN-' + no;
    var prompts = String(st.prompts || '').split(/\n-{3,}\n/).filter(function (x) { return x.trim(); });
    var row = new Array(NCOLS).fill('');
    row[C.story_id - 1] = id;
    row[C.researched - 1] = "'" + nowIst_();
    row[C.published - 1] = "'" + (st.published || '');
    row[C.headline_ta - 1] = st.tamil_headline; row[C.headline_en - 1] = st.english_headline;
    row[C.category - 1] = st.category; row[C.location - 1] = st.location; row[C.importance - 1] = st.importance;
    row[C.verification - 1] = st.verification || 'FREE-MODEL DRAFT - not checked by Claude yet';
    row[C.source - 1] = st.source || '';
    row[C.caption - 1] = st.caption; row[C.email_sent - 1] = 'Sent';
    row[C.review - 1] = 'Auto'; row[C.post_to - 1] = st.post_to; row[C.reel - 1] = 'Yes';
    row[C.reel_script - 1] = st.reel_script;
    row[C.slides_spec - 1] = typeof st.slides_spec === 'string' ? st.slides_spec : JSON.stringify(st.slides_spec);
    row[C.post_status - 1] = 'Awaiting images';
    row[C.notes - 1] = nowIst_() + ' ' + (st.note || 'free-model draft');
    row[C.batch - 1] = batch; row[C.prompts - 1] = prompts.join('\n---\n');
    // the research job already made ALL images with the free AI image API: queue the story for posting, no email needed for it
    var made = (st.images && st.images.length >= prompts.length && prompts.length) ? st.images : null;
    if (made) {
      row[C.images - 1] = JSON.stringify(made);
      row[C.post_status - 1] = 'Queued';
      row[C.notes - 1] += ' | ' + made.length + ' images made automatically (free AI image API)';
      auto++;
    } else if (st.auto_images) {
      // images could not be made in the research run: the posting job (every 5 minutes) tries the image models again, no 2-hour wait
      row[C.post_status - 1] = 'Auto images';
      row[C.notes - 1] += ' | images not made yet - the posting job makes them';
    }
    rows.push(row);
    if (!made && !st.auto_images) items.push({ id: id, ta: st.tamil_headline, en: st.english_headline, post_to: st.post_to, importance: st.importance, post_time: st.post_time, prompts: prompts });
  });
  sh.getRange(sh.getLastRow() + 1, 1, rows.length, NCOLS).setValues(rows);
  var again = reofferItems_(b.reoffer_ids, batch);       // stories of earlier rounds that still wait for images go into the same e-mail
  items = again.concat(items);
  items.forEach(function (it) { sendPromptEmail_(batch, [it]); });      // ONE e-mail per news
  return { ok: true, added: rows.length, auto_queued: auto, emailed: items.length, reoffered: again.length, batch: batch, first: 'RN-' + (no - rows.length + 1) };
}


var PROMPT_RULES = 'READ THIS FIRST - STRICT RULES (follow every one):\n' +
  '0. Do NOT put several scenes into one picture. The images in the last attempt came out as collages of 3-5 vertical strips - that is WRONG and unusable.\n' +
  '1. Make EACH image as its OWN separate single image: one prompt = one image generation = one file. Do ONE image generation per prompt, one after another. Never combine prompts. If you are about to merge two prompts into one picture, STOP and make them separately.\n' +
  '1b. Every image is ONE continuous photograph taken with ONE camera from ONE angle: no panels, no strips, no tiles, no borders, no split frames, no inset pictures, no captions or labels written on the image.\n' +
  '2. NEVER make a collage, grid, contact sheet, storyboard, multi-panel, split-screen or "all scenes in one picture". Every image shows exactly ONE scene filling the whole frame.\n' +
  '3. Every image is a single full-frame tall vertical 9:16 portrait, 1080x1920 or larger, highest resolution, MAXIMUM CLARITY: tack-sharp focus over the whole picture, crisp detail, clean and noise-free, no blur or soft focus, no painterly or over-smoothed AI look, photorealistic, no text, letters, numbers or logos. Generate at the largest size and best quality available.\n' +
  '4. Do NOT crop, resize, compress, sharpen or edit the images after creating them. Use the original generated image files.\n' +
  '5. Name each file exactly as its FILE name below (for example RN-26_1.png).\n' +
  '6. At the end, if you can run code: make ZIP files with the separate original image files (store them as they are, no re-compression, no folders, no resizing). Each zip must be SMALLER THAN 24 MB (email limit). Put WHOLE stories in a zip: never split one story across two zips. Use as many zips as needed (usually about 15-20 images per zip) and name them BATCH_part1.zip, BATCH_part2.zip, BATCH_part3.zip and so on. If everything fits under 24 MB, make just BATCH.zip. Give me a separate downloadable link for each zip and tell me its size in MB and the number of images in it. If you cannot make zips, list every file so I can download each one.\n' +
  '7. Do not skip any image and do not change the prompts.\n';

/** items: [{id, ta, en, post_to, importance, post_time, prompts[]}] -> ONE .md file in Drive + ONE email */
function sendPromptEmail_(batch, items) {
  var total = 0, lines = [], md = [], summary = [];
  items.forEach(function (it) {
    total += it.prompts.length;
    lines.push(it.id + ' | ' + it.ta + ' | ' + it.prompts.length + ' images | ' + it.post_to + ' | ' + it.importance + ' | post: ' + (it.post_time || 'right after your reply'));
    summary.push('| ' + it.id + ' | ' + it.ta + ' | ' + it.en + ' | ' + it.prompts.length + ' |');
    md.push('## STORY ' + it.id + ' - ' + it.ta + ' (' + it.en + ') - ' + it.prompts.length + ' images');
    it.prompts.forEach(function (pr, k) { md.push('### FILE: ' + it.id + '_' + (k + 1) + '.png\nCreate this as ONE separate single image (not a collage), with maximum clarity and sharpness:\n' + pr.trim() + '\n'); });
  });
  var head = '# TRICHY360 IMAGE PROMPTS - ' + batch + '\n## INSTRUCTIONS FOR CHATGPT (copy this whole file into ChatGPT, then follow it)\nYou are an image generator. Total separate images to create: ' + total + '.\n' +
    PROMPT_RULES.replace('BATCH.zip', batch + '.zip') + '## SUMMARY\n| Story ID | Tamil headline | English headline | Images |\n|---|---|---|---|\n' + summary.join('\n') + '\n\n';
  var file = DriveApp.getFolderById(ROOT_FOLDER_ID).createFile(batch + '_ChatGPT_Image_Prompts.md', head + md.join('\n'), MimeType.PLAIN_TEXT);
  var body = 'I am waiting for your images. Nothing will be posted until you reply to this email with the zip.\n\n' +
    'IMAGE PROMPT FILE (open, download, paste into ChatGPT): ' + file.getUrl() + '\n\nTHIS CHECK:\n' + lines.join('\n') + '\nTotal images: ' + total +
    '\n\nIMPORTANT: ChatGPT must make EACH image separately (no collage, no strips) and keep the original files - the new file says so. If ChatGPT still makes a collage, send it this message: "Wrong. Delete the collage. Make ONLY image RN-xx_1 as one single full-frame photograph, nothing else. Then wait." and continue one image at a time.\n\nHOW TO REPLY:\n(1) Give the .md file to ChatGPT.\n(2) ChatGPT makes all images one by one (names like RN-26_1.png) and puts them in zips of WHOLE stories, each zip under 24 MB (more zips if needed).\n(3) REPLY to this email once for EACH zip, with that zip attached.\n(4) Leave the reply text empty.\n(5) Reply from ' + OWNER_EMAIL +
    ' - the post is built and published about 20-40 minutes after your reply, the same day.\n\nDetails, captions and sources: ' + SHEET_LINK;
  var subj = items.length === 1 ? '[TRICHY360 IMAGES NEEDED] ' + items[0].id + ' ' + batch + ' - ' + items[0].ta.slice(0, 50) : '[TRICHY360 IMAGES NEEDED] ' + batch + ' - ' + items.length + ' stories - ' + total + ' images';
  GmailApp.sendEmail(OWNER_EMAIL, subj, body);
}

/** Puts the given stories (not posted yet) back to "Awaiting images" under the batch id and returns the e-mail items for them. */
function reofferItems_(ids, batch) {
  var sh = sheet_();
  var want = {};
  (ids || []).forEach(function (x) { want[x] = true; });
  var last = sh.getLastRow();
  if (last < 2) return [];
  var data = sh.getRange(2, 1, last - 1, NCOLS).getValues();
  var items = [];
  for (var i = 0; i < data.length; i++) {
    var r = rowObj_(data[i], i + 2);
    if (!want[r.story_id]) continue;
    if (r.coimbatore_link || r.reel_link) continue;           // already posted: never touch
    var prompts = String(r.prompts || '').split(/\n-{3,}\n/).filter(function (x) { return x.trim(); });
    if (!prompts.length) continue;
    sh.getRange(r.row, C.post_status).setValue('Awaiting images');
    sh.getRange(r.row, C.images).setValue('');
    sh.getRange(r.row, C.batch).setValue(batch);
    appendNote_(sh, r.row, r.notes, nowIst_() + ' images asked again (batch ' + batch + ')');
    items.push({ id: r.story_id, ta: r.headline_ta, en: r.headline_en, post_to: r.post_to, importance: r.importance, post_time: 'right after your reply', prompts: prompts });
  }
  return items;
}

/** body: {ids:["RN-24",...]} Stories that are NOT posted yet go back to "Awaiting images" under ONE new batch, with ONE new email + prompt file. */
function reoffer_(b) {
  var batch = 'B' + Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyyMMdd-HHmm');
  var items = reofferItems_(b.ids, batch);
  if (!items.length) return { ok: true, offered: 0 };
  sendPromptEmail_(batch, items);
  return { ok: true, offered: items.length, batch: batch };
}


// Run once from the editor (Run → retryMessage) to process a ready-reel e-mail again: put its Gmail message id below first.
function retryMessage() {
  var msg = GmailApp.getMessageById('MESSAGE_ID_HERE');
  var report = readyOne_(msg);
  GmailApp.sendEmail(OWNER_EMAIL, '[TRICHY360 RETRY REPORT] ready reels', report.join('\n') + '\n\nSheet: ' + SHEET_LINK);
}


// ================================================================== owner's pick (owner 1 Nov)
// 6 AM and 4 PM: the GitHub job sends the news list (Dinamalar + Dinamani Coimbatore) -> this makes a GOOGLE FORM with a check box for
// every news and e-mails its link -> the owner ticks and presses Submit -> GitHub writes and posts EVERY ticked news.
// No submit in 1 hour: GitHub posts the top 8. (A Google Form opens on any phone / computer, with any number of Google accounts signed in.)
var PICK_TAB = 'Picks';
var PICK_HEAD = ['Round', 'Token', 'Created (IST)', 'Deadline', 'Items', 'Auto picked', 'Owner ticked', 'Submitted (IST)', 'Form id'];

/** Run ONCE from the editor after pasting this code (Run -> authorizeForms): Google asks for the Forms permission. */
function authorizeForms() {
  var f = FormApp.create('Coimbatore 360 - permission test');
  DriveApp.getFileById(f.getId()).setTrashed(true);
  Logger.log('Google Forms permission OK');
}

function picksSheet_() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sh = ss.getSheetByName(PICK_TAB);
  if (!sh) { sh = ss.insertSheet(PICK_TAB); sh.appendRow(PICK_HEAD); sh.setFrozenRows(1); }
  if (sh.getRange(1, PICK_HEAD.length).getValue() !== PICK_HEAD[PICK_HEAD.length - 1]) sh.getRange(1, 1, 1, PICK_HEAD.length).setValues([PICK_HEAD]);
  return sh;
}
function pickRow_(round) {
  var sh = picksSheet_(), last = sh.getLastRow();
  if (last < 2) return null;
  var vals = sh.getRange(2, 1, last - 1, PICK_HEAD.length).getValues();
  for (var i = vals.length - 1; i >= 0; i--) if (String(vals[i][0]) === String(round)) return { row: i + 2, v: vals[i] };
  return null;
}
function esc_(t) { return String(t || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function pickFolder_() {
  var root = DriveApp.getFolderById(ROOT_FOLDER_ID), it = root.getFoldersByName('Pick forms');
  return it.hasNext() ? it.next() : root.createFolder('Pick forms');
}

function makePickForm_(b, label, items) {
  var form = FormApp.create('கோவை செய்திகள் – ' + label + ' – ' + Utilities.formatDate(new Date(), 'Asia/Kolkata', 'dd MMM yyyy'));
  try { DriveApp.getFileById(form.getId()).moveTo(pickFolder_()); } catch (err) { }
  form.setDescription('பதிவிட வேண்டிய செய்திகளைத் தேர்வு செய்து Submit செய்யுங்கள். தேர்வு செய்த ஒவ்வொரு செய்தியும் எழுதப்பட்டு, ரீல் செய்து உடனே பதிவிடப்படும்.\n' +
    b.deadline + '-க்குள் Submit செய்யவில்லை என்றால், முதல் ' + (b.auto_top || 8) + ' செய்திகள் தானாக பதிவிடப்படும்.\n⏳ = முந்தைய பட்டியலில் இருந்து (இன்னும் பதிவிடவில்லை)');
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setShowLinkToRespondAgain(true);      // more news can be ticked later: they are added
  form.setProgressBar(false);
  form.setConfirmationMessage('✅ தேர்வு செய்யப்பட்டது. எழுதி, ரீல் செய்து, உடனே பதிவிடப்படும். (கூடுதலாக தேர்வு செய்ய மீண்டும் Submit செய்யலாம்.)');
  try { form.setRequireLogin(false); } catch (err) { }
  var choices = items.map(function (x, i) {
    var sum = String(x.summary || '').slice(0, 140);
    return (i + 1) + '. ' + (x.leftover ? '⏳ ' : '') + x.title + (sum ? ' — ' + sum : '') + ' (' + x.source + ')';
  });
  form.addCheckboxItem().setTitle('செய்திகள் (' + items.length + ')').setChoiceValues(choices).setRequired(false);
  return form;
}

function pickList_(b) {
  var sh = picksSheet_();
  var token = Utilities.getUuid().replace(/-/g, '');
  var items = b.items || [];
  var label = /morning/.test(b.round) ? 'காலை' : 'மாலை';
  var form = makePickForm_(b, label, items);
  var url = form.getPublishedUrl();
  var old = pickRow_(b.round);
  var row = [b.round, token, nowIst_(), b.deadline || '', JSON.stringify(items), '', '', '', form.getId()];
  if (old) sh.getRange(old.row, 1, 1, row.length).setValues([row]); else sh.appendRow(row);
  var newOnes = items.filter(function (x) { return !x.leftover; }), left = items.filter(function (x) { return x.leftover; });
  function block(list, start) {
    return list.map(function (x, i) {
      return '<tr><td style="padding:8px;vertical-align:top;font-weight:bold">' + (start + i) + '</td><td style="padding:8px">' +
        '<div style="font-size:16px;font-weight:bold">' + esc_(x.title) + '</div>' +
        '<div style="color:#444;margin:4px 0">' + esc_(x.summary) + '</div>' +
        '<div style="color:#888;font-size:12px">' + esc_(x.category) + ' · ' + esc_(x.source) + ' · ' + esc_(String(x.published || '').slice(0, 16).replace('T', ' ')) +
        ' · <a href="' + esc_(x.url) + '">செய்தி</a></div></td></tr>';
    }).join('');
  }
  var btn = '<a href="' + url + '" style="display:inline-block;background:#c62828;color:#fff;padding:14px 26px;border-radius:8px;text-decoration:none;font-size:18px;font-weight:bold">✅ செய்திகளைத் தேர்வு செய்ய</a>';
  var html = '<div style="font-family:Arial,sans-serif;max-width:680px">' +
    '<h2 style="margin:0 0 6px">கோவை செய்திகள் – ' + label + ' (' + items.length + ')</h2>' +
    '<div style="color:#555;margin-bottom:12px">செய்தி வெளியான நேரம்: ' + esc_(b.window) + '<br>' +
    b.deadline + '-க்குள் தேர்வு செய்யவில்லை என்றால், முதல் ' + (b.auto_top || 8) + ' செய்திகள் தானாக பதிவிடப்படும்.</div>' + btn +
    (newOnes.length ? '<h3 style="margin:18px 0 4px">🆕 புதிய செய்திகள்</h3><table>' + block(newOnes, 1) + '</table>' : '') +
    (left.length ? '<h3 style="margin:18px 0 4px">⏳ முந்தைய பட்டியலில் இருந்து (இன்னும் பதிவிடவில்லை)</h3><table>' + block(left, newOnes.length + 1) + '</table>' : '') +
    '<p>' + btn + '</p><p style="color:#888;font-size:12px">தேர்வு பக்கம் (Google Form): ' + url + '</p></div>';
  var plain = 'கோவை செய்திகள் – ' + label + ' (' + items.length + ')\nதேர்வு செய்ய: ' + url + '\n\n' +
    items.map(function (x, i) { return (i + 1) + '. ' + x.title + '\n   ' + x.summary + '\n   ' + x.source + ' ' + x.url; }).join('\n\n');
  GmailApp.sendEmail(OWNER_EMAIL, '[TRICHY360 PICK] கோவை செய்திகள் – ' + label + ' (' + items.length + ') – தேர்வு செய்யவும்', plain, { htmlBody: html });
  return { ok: true, round: b.round, items: items.length, form: url };
}

function pickAuto_(b) {
  var r = pickRow_(b.round);
  if (!r) return { ok: false, error: 'no such round' };
  picksSheet_().getRange(r.row, 6).setValue(JSON.stringify(b.ids || []));
  return { ok: true };
}

/** the owner's ticks: every Google Form response of the round (several submits are added together) + any ids written in "Owner ticked" */
function pickStatus_(round) {
  var r = pickRow_(round);
  if (!r) return { ok: true, submitted: false };
  var items = JSON.parse(String(r.v[4] || '[]'));
  var ids = [], at = String(r.v[7] || ''), submitted = false;
  var ticked = String(r.v[6] || '');
  if (ticked) { submitted = true; JSON.parse(ticked).forEach(function (x) { if (ids.indexOf(x) < 0) ids.push(x); }); }
  var fid = String(r.v[8] || '');
  if (fid) {
    var resps = FormApp.openById(fid).getResponses();
    resps.forEach(function (resp) {
      submitted = true;
      at = Utilities.formatDate(resp.getTimestamp(), 'Asia/Kolkata', 'dd MMM yyyy, HH:mm');
      resp.getItemResponses().forEach(function (ir) {
        var v = ir.getResponse();
        (Array.isArray(v) ? v : [v]).forEach(function (txt) {
          var m = String(txt).match(/^(\d+)\./);
          var it = m ? items[+m[1] - 1] : null;
          if (it && ids.indexOf(it.id) < 0) ids.push(it.id);
        });
      });
    });
  }
  return { ok: true, submitted: submitted, ids: ids, at: at };
}

// the older check-box page (kept so an old e-mail link still answers)
function pickPage_(e) {
  return HtmlService.createHtmlOutput('<p style="font-family:Arial;font-size:18px">புதிய மின்னஞ்சலில் உள்ள Google Form இணைப்பைப் பயன்படுத்துங்கள்.</p>');
}
function submitPicks(round, token, ids) {
  return 'புதிய மின்னஞ்சலில் உள்ள Google Form இணைப்பைப் பயன்படுத்துங்கள்.';
}

// ------------------------------------------------------------------ comment replies (owner 11 Nov) - GOOGLE FORM, like the news picks
// The GitHub job (poster/comments.py) sends new Instagram comments with 5-7 reply options (action commentNew). Apps Script makes ONE
// Google Form per page and batch: for each comment the full news, the comment, tick boxes (one or more replies), an own-reply box and an
// action (Reply / Skip / Hide). The form link is e-mailed; it opens on any phone or computer, with no Google account needed.
// NOTHING is posted until the owner presses Submit. commentPoll (every 5 minutes, see setupCommentPoll) reads the answers and posts.
var COMMENTS_TAB = 'Comments';
var COMMENT_COLS = ['received_ist', 'page', 'comment_id', 'media_id', 'permalink', 'post_title', 'user', 'text', 'kind',
                    'opt1', 'opt2', 'opt3', 'secret', 'status', 'reply', 'reply_id', 'done_ist', 'received_ms', 'post_text', 'opts_json',
                    'form_id', 'form_no'];
var COMMENT_HOURS = 48;
var COMMENT_MAX_FORM = 20;      // comments per form (a form holds up to 300 questions)
var IG_REPLY_HOST = 'https://graph.instagram.com/v23.0/';
var COMMENT_ACTIONS = ['Reply (tick one or more, and/or type your own)', 'Skip', 'Hide this comment'];

function commentEsc_(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function commentsSheet_() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sh = ss.getSheetByName(COMMENTS_TAB);
  if (!sh) {
    sh = ss.insertSheet(COMMENTS_TAB);
    sh.appendRow(COMMENT_COLS);
    sh.setFrozenRows(1);
  } else if (sh.getLastColumn() < COMMENT_COLS.length || sh.getRange(1, COMMENT_COLS.length).getValue() !== COMMENT_COLS[COMMENT_COLS.length - 1]) {
    sh.getRange(1, 1, 1, COMMENT_COLS.length).setValues([COMMENT_COLS]);      // an older tab: the header is updated
  }
  return sh;
}

function commentRows_() {
  var sh = commentsSheet_();
  var n = sh.getLastRow();
  if (n < 2) return [];
  var vals = sh.getRange(2, 1, n - 1, COMMENT_COLS.length).getValues();
  return vals.map(function (v, i) {
    var o = { row: i + 2 };
    COMMENT_COLS.forEach(function (c, k) { o[c] = v[k]; });
    return o;
  });
}

function commentOptions_(r) {
  try { var o = JSON.parse(r.opts_json || '[]'); if (o.length) return o; } catch (e) {}
  return [r.opt1, r.opt2, r.opt3].filter(function (x) { return x; });
}

// GET action=commentsSeen -> the comment ids already handled (the job never sends a comment twice)
function commentsSeen_() {
  return commentRows_().map(function (r) { return String(r.comment_id); });
}

// POST action=commentNew {page, items:[{comment_id, media_id, permalink, post_title, post_text, user, text, kind, options:[..]}]}
function commentNew_(b) {
  var sh = commentsSheet_();
  var seen = {};
  commentsSeen_().forEach(function (id) { seen[id] = true; });
  var fresh = [];
  (b.items || []).forEach(function (it) {
    if (it.comment_id && !seen[String(it.comment_id)] && fresh.length < COMMENT_MAX_FORM) fresh.push(it);
  });
  // owner 12 Nov: normal comments (not critical) are only recorded, so they are never checked or e-mailed again
  var ign = (b.ignored || []).filter(function (id) { return id && !seen[String(id)]; });
  if (ign.length) {
    sh.getRange(sh.getLastRow() + 1, 1, ign.length, COMMENT_COLS.length).setValues(ign.map(function (id) {
      var r = COMMENT_COLS.map(function () { return ''; });
      r[COMMENT_COLS.indexOf('received_ist')] = nowIst_(); r[COMMENT_COLS.indexOf('page')] = b.page;
      r[COMMENT_COLS.indexOf('comment_id')] = String(id); r[COMMENT_COLS.indexOf('kind')] = 'not critical';
      r[COMMENT_COLS.indexOf('status')] = 'ignored'; r[COMMENT_COLS.indexOf('received_ms')] = Date.now();
      return r;
    }));
  }
  if (!fresh.length) return { ok: true, added: 0, ignored: ign.length };
  var form = commentFormMake_(b.page, fresh);
  var fid = form.getId();
  var rows = fresh.map(function (it, i) {
    var o = it.options || [];
    return [nowIst_(), b.page, String(it.comment_id), String(it.media_id || ''), it.permalink || '', it.post_title || '', it.user || '',
            it.text || '', it.kind || '', o[0] || '', o[1] || '', o[2] || '', '', 'waiting', '', '', '', Date.now(),
            String(it.post_text || '').slice(0, 3000), JSON.stringify(o.slice(0, 7)), fid, i + 1];
  });
  sh.getRange(sh.getLastRow() + 1, 1, rows.length, COMMENT_COLS.length).setValues(rows);
  commentMail_(b.page, fresh, form);
  return { ok: true, added: fresh.length, ignored: ign.length };
}

// the Google Form of one batch: per comment a section (news + comment), the action, the reply tick boxes and an own-reply box
function commentFormMake_(page, items) {
  var label = (typeof PAGE_LABEL !== 'undefined' && PAGE_LABEL[page]) || page;
  var form = FormApp.create(label + ' - comment replies - ' + Utilities.formatDate(new Date(), 'Asia/Kolkata', 'dd MMM yyyy HH:mm'));
  try { DriveApp.getFileById(form.getId()).moveTo(pickFolder_()); } catch (err) { }
  form.setDescription('For each comment: choose the action, tick one or more replies, or type your own, then press Submit. ' +
    'Nothing is posted on Instagram before you press Submit. Comments older than ' + COMMENT_HOURS + ' hours are not posted.');
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setProgressBar(true);
  form.setConfirmationMessage('✅ Received. The chosen replies are posted on Instagram within about 5 minutes.');
  try { form.setRequireLogin(false); } catch (err) { }
  items.forEach(function (it, i) {
    var n = i + 1;
    var news = String(it.post_text || it.post_title || '').slice(0, 1500);
    form.addSectionHeaderItem().setTitle('Comment ' + n + ' · @' + (it.user || '')).setHelpText(
      'NEWS: ' + news + '\n\nCOMMENT: ' + (it.text || '') + '\n\nTYPE: ' + (it.kind || '') + '\nPOST: ' + (it.permalink || ''));
    form.addMultipleChoiceItem().setTitle('C' + n + ' · Action').setChoiceValues(COMMENT_ACTIONS).setRequired(true);
    var opts = [];
    (it.options || []).forEach(function (o) {
      o = String(o || '').trim().slice(0, 400);
      if (o && opts.indexOf(o) < 0 && opts.length < 7) opts.push(o);
    });
    if (opts.length) form.addCheckboxItem().setTitle('C' + n + ' · Replies (tick one or more)').setChoiceValues(opts).setRequired(false);
    form.addParagraphTextItem().setTitle('C' + n + ' · Your own reply (optional - used instead of the ticked replies)').setRequired(false);
  });
  return form;
}

function commentMail_(page, fresh, form) {
  var label = (typeof PAGE_LABEL !== 'undefined' && PAGE_LABEL[page]) || page;
  var url = form.getPublishedUrl();
  var html = '<div style="font-family:Arial,sans-serif;font-size:15px">' +
    '<p><b>' + fresh.length + ' new comment(s) on ' + commentEsc_(label) + '.</b></p>' +
    '<p><a href="' + url + '" style="display:inline-block;background:#1a73e8;color:#fff;padding:12px 20px;border-radius:8px;' +
    'text-decoration:none;font-size:17px">Open the reply form</a></p>' +
    '<p style="color:#666">The form shows the full news for each comment. Choose the action, tick one or more replies or type your own, ' +
    'then press Submit. Nothing is posted before you press Submit.</p><ul>';
  fresh.forEach(function (it) {
    html += '<li><b>@' + commentEsc_(it.user) + '</b>: ' + commentEsc_(it.text) + ' <span style="color:#666">(' + commentEsc_(it.post_title) + ')</span></li>';
  });
  html += '</ul></div>';
  GmailApp.sendEmail(OWNER_EMAIL, '[' + label + ' COMMENTS] ' + fresh.length + ' new - open the reply form',
    'Open the reply form: ' + url, { htmlBody: html });
}

function commentOpen_(r) {
  var t = Number(r.received_ms) || 0;
  if (!t || (Date.now() - t) > COMMENT_HOURS * 3600 * 1000) return 'older than ' + COMMENT_HOURS + ' hours';
  return '';
}

// every 5 minutes (set up once by setupCommentPoll): reads the owner's submitted forms and posts the chosen replies
function commentPoll() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) return;
  try {
    var byForm = {};
    commentRows_().forEach(function (r) {
      if (r.status === 'waiting' && r.form_id) (byForm[r.form_id] = byForm[r.form_id] || []).push(r);
    });
    Object.keys(byForm).forEach(function (fid) {
      var resps;
      try { resps = FormApp.openById(fid).getResponses(); } catch (err) { Logger.log('form ' + fid + ': ' + err); return; }
      byForm[fid].forEach(function (r) { commentHandle_(r, resps); });
    });
  } finally {
    lock.releaseLock();
  }
}

// the newest submitted answer for this comment's section of the form (its number = form_no)
function commentAnswer_(r, resps) {
  var n = Number(r.form_no);
  for (var i = resps.length - 1; i >= 0; i--) {
    var m = {};
    resps[i].getItemResponses().forEach(function (ir) { m[ir.getItem().getTitle()] = ir.getResponse(); });
    var action = m['C' + n + ' · Action'];
    if (action) return { action: action, ticked: m['C' + n + ' · Replies (tick one or more)'] || [], own: String(m['C' + n + ' · Your own reply (optional - used instead of the ticked replies)'] || '').trim() };
  }
  return null;
}

function commentHandle_(r, resps) {
  var sh = commentsSheet_();
  var col = function (name) { return COMMENT_COLS.indexOf(name) + 1; };
  var set = function (name, v) { sh.getRange(r.row, col(name)).setValue(v); };
  var a = commentAnswer_(r, resps);
  if (!a) return;                                       // not submitted yet
  if (String(r.comment_id).indexOf('TEST-') === 0) { set('status', 'test'); return; }      // the sample e-mail: never posted
  if (commentOpen_(r)) { set('status', 'expired'); set('done_ist', nowIst_()); return; }
  if (a.action === COMMENT_ACTIONS[1]) { set('status', 'skipped'); set('done_ist', nowIst_()); return; }
  var tok = token_(r.page);
  if (a.action === COMMENT_ACTIONS[2]) {
    var h = UrlFetchApp.fetch(IG_REPLY_HOST + r.comment_id, { method: 'post', muteHttpExceptions: true, payload: { hide: 'true', access_token: tok } });
    set('status', h.getResponseCode() === 200 ? 'hidden' : 'error');
    set('reply', h.getResponseCode() === 200 ? '' : 'hide failed: ' + h.getContentText().slice(0, 200));
    set('done_ist', nowIst_());
    return;
  }
  var ticked = (a.ticked instanceof Array) ? a.ticked : (a.ticked ? [a.ticked] : []);
  var msg = (a.own || ticked.join(' ')).trim();
  if (!msg) return;                                     // Reply chosen but no text: left waiting (the owner can submit again)
  var res = UrlFetchApp.fetch(IG_REPLY_HOST + r.comment_id + '/replies', { method: 'post', muteHttpExceptions: true,
    payload: { message: msg.slice(0, 2200), access_token: tok } });
  if (res.getResponseCode() !== 200) {
    set('status', 'error');
    set('reply', 'Instagram did not accept: ' + res.getContentText().slice(0, 200));
    set('done_ist', nowIst_());
    return;
  }
  set('status', 'replied');
  set('reply', msg);
  set('reply_id', (JSON.parse(res.getContentText()) || {}).id || '');
  set('done_ist', nowIst_());
}

// run ONCE from the Apps Script editor (Run -> setupCommentPoll, then Review permissions -> Allow): starts the 5-minute check
function setupCommentPoll() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'commentPoll') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('commentPoll').timeBased().everyMinutes(5).create();
  Logger.log('Comment replies: the submitted forms are checked every 5 minutes');
}
