// Translation dictionary + resolver for the Anchor student app.
// Plain JS (NOT Babel) — loaded via <script src> in index.html BEFORE the
// type="text/babel" component scripts, so window.tStr exists by first render.
//
// window.tStr(key, lang, type)
//   lang : 'EN' | 'BN' | 'BI'   (case-insensitive; anything unknown → 'EN')
//   type : 'ui' (default) | 'content'
//   'BI' is the bilingual / "Both" mode: UI chrome stays English, while
//   long-form content (type='content') renders in Bangla.
//   Resolution order: requested dict → English → raw key. Never blank, never throws.

(function () {
  var EN = {
    // ── Bottom nav ────────────────────────────────────────────
    nav_home:    'Home',
    nav_cases:   'My Cases',
    nav_alert:   'Alert',
    nav_chat:    'Anchor AI',
    nav_profile: 'Profile',

    // ── Header / mode ─────────────────────────────────────────
    hdr_campus:   'Campus',
    hdr_national: 'National · BD',
    c2c_campus:        'Campus',
    c2c_campus_sub:    'DIU',
    c2c_national:      'National',
    c2c_national_sub:  'Bangladesh',

    // ── Common buttons ────────────────────────────────────────
    btn_back:   'Back',
    btn_cancel: 'Cancel',
    btn_save:   'Save changes',
    btn_saving: 'Saving…',

    // ── Home ──────────────────────────────────────────────────
    home_choose_context:  'Choose your context',
    home_campus_tag:      'Governance, complaints, and routine — within Daffodil.',
    home_national_tag:    'Legal aid, safety, and verification — across Bangladesh.',
    home_national_title:  'National · Bangladesh',
    home_national_sub:    'Legal aid, safety & verification',
    home_alert_eyebrow:   'Phase 2 alert',
    home_alert_text:      'Hold 4 seconds to broadcast emergency',
    home_alert_hold:      'Hold',
    home_quick_actions:   'Quick actions',
    home_routes:          'routes',
    home_my_filings:      'My filings · recent',
    home_view_all:        'View all →',
    home_no_filings_title: 'No filings yet',
    home_no_filings_sub:   'Tap to file a complaint, report, or grievance',
    home_campus_verified: 'Campus verified',
    home_verified_news:   'Verified news',
    home_newspaper:       'Newspaper →',

    // ── Home tiles · Campus ───────────────────────────────────
    tile_file:           'File',
    tile_file_sub:       'Complaint · Report · Grievance',
    tile_apply:          'Apply formally',
    tile_apply_sub:      'AI-drafted · 13 templates',
    tile_routine:        'Academic routine',
    tile_routine_sub:    'Today · 4 classes',
    tile_notices:        'University notices',
    tile_notices_sub:    '3 new this week',
    tile_my_filings:     'My filings',
    tile_my_filings_sub: 'Track complaints & reports',
    tile_classroom:      'Report classroom',
    tile_classroom_sub:  'AC · Projector · Net',
    tile_feed:           'Publish news',
    tile_feed_sub_campus: 'Notices & rumours',
    tile_rate:           'Rate department',
    tile_rate_sub:       'SWE · CSE · BBA',

    // ── Home tiles · National ─────────────────────────────────
    tile_fir:            'Draft FIR / GD',
    tile_fir_sub:        'AI-assisted document',
    tile_lawyer:         'Find a lawyer',
    tile_lawyer_sub:     'End-to-end encrypted',
    tile_zones:          'Red zone map',
    tile_zones_sub:      'Dhaka · live overlay',
    tile_rights:         'Know your rights',
    tile_rights_sub:     'BD Penal Code · DV Act',
    tile_feed_sub_national: 'Human-moderated',
    tile_officer:        'Officer scorecard',
    tile_officer_sub:    'Public accountability',

    // ── Profile / Settings groups ─────────────────────────────
    set_group_legal:         'Legal',
    set_group_prefs:         'Preferences',
    set_group_safety:        'Safety',
    set_group_data:          'Data',
    set_group_location:      'Location',
    set_group_notifications: 'Notifications',
    set_messages:        'Messages',
    set_messages_val:    'Encrypted',
    set_apply_lawyer:    'Apply as a Lawyer',
    set_my_lawyer:       'My lawyer profile',
    set_lawyer_verified: 'Verified',
    set_lawyer_pending:  'Verification',
    set_language:        'Language',
    set_notifications:   'Notifications',
    set_anonymity:       'Default anonymity',
    set_anonymity_val:   'Always ask',
    set_dms:             "Dead Man's Switch",
    set_2fa:             'Two-factor auth',
    set_2fa_off:         'Not set up',
    set_contacts:        'Trusted contacts',
    set_export:          'Export my data',
    set_delete:          'Delete account',
    set_delete_val:      'Permanent',
    set_nearby_alerts:   'Nearby alerts',
    set_safety_notif:    'Safety alert notifications',
    set_group_appearance: 'Appearance',
    set_dark_mode:        'Dark mode',
    set_dark_mode_on:     'On — easier on the eyes at night',
    set_dark_mode_off:    'Off — following a light theme',

    // ── Language picker card ──────────────────────────────────
    lang_title:          'Language',
    lang_question:       'How should Anchor speak to you?',
    lang_switch_anytime: 'Switch anytime · we understand both',
  };

  var BN = {
    // ── Bottom nav ────────────────────────────────────────────
    nav_home:    'হোম',
    nav_cases:   'আমার মামলা',
    nav_alert:   'সতর্কতা',
    nav_chat:    'অ্যাঙ্কর এআই',
    nav_profile: 'প্রোফাইল',

    // ── Header / mode ─────────────────────────────────────────
    hdr_campus:   'ক্যাম্পাস',
    hdr_national: 'জাতীয় · বিডি',
    c2c_campus:        'ক্যাম্পাস',
    c2c_campus_sub:    'ডিআইইউ',
    c2c_national:      'জাতীয়',
    c2c_national_sub:  'বাংলাদেশ',

    // ── Common buttons ────────────────────────────────────────
    btn_back:   'ফিরে যান',
    btn_cancel: 'বাতিল',
    btn_save:   'পরিবর্তন সংরক্ষণ',
    btn_saving: 'সংরক্ষণ হচ্ছে…',

    // ── Home ──────────────────────────────────────────────────
    home_choose_context:  'আপনার প্রসঙ্গ বেছে নিন',
    home_campus_tag:      'প্রশাসন, অভিযোগ ও রুটিন — ড্যাফোডিলের ভেতরে।',
    home_national_tag:    'আইনি সহায়তা, নিরাপত্তা ও যাচাই — সারা বাংলাদেশে।',
    home_national_title:  'জাতীয় · বাংলাদেশ',
    home_national_sub:    'আইনি সহায়তা, নিরাপত্তা ও যাচাই',
    home_alert_eyebrow:   'ফেজ ২ সতর্কতা',
    home_alert_text:      'জরুরি বার্তা পাঠাতে ৪ সেকেন্ড ধরে রাখুন',
    home_alert_hold:      'ধরে রাখুন',
    home_quick_actions:   'দ্রুত কাজ',
    home_routes:          'রুট',
    home_my_filings:      'আমার ফাইলিং · সাম্প্রতিক',
    home_view_all:        'সব দেখুন →',
    home_no_filings_title: 'এখনও কোনো ফাইলিং নেই',
    home_no_filings_sub:   'অভিযোগ, রিপোর্ট বা নালিশ দাখিল করতে ট্যাপ করুন',
    home_campus_verified: 'ক্যাম্পাস যাচাইকৃত',
    home_verified_news:   'যাচাইকৃত সংবাদ',
    home_newspaper:       'সংবাদপত্র →',

    // ── Home tiles · Campus ───────────────────────────────────
    tile_file:           'দাখিল করুন',
    tile_file_sub:       'অভিযোগ · রিপোর্ট · নালিশ',
    tile_apply:          'আনুষ্ঠানিক আবেদন',
    tile_apply_sub:      'এআই-খসড়া · ১৩ টেমপ্লেট',
    tile_routine:        'একাডেমিক রুটিন',
    tile_routine_sub:    'আজ · ৪ ক্লাস',
    tile_notices:        'বিশ্ববিদ্যালয় নোটিশ',
    tile_notices_sub:    'এই সপ্তাহে ৩টি নতুন',
    tile_my_filings:     'আমার ফাইলিং',
    tile_my_filings_sub: 'অভিযোগ ও রিপোর্ট ট্র্যাক করুন',
    tile_classroom:      'ক্লাসরুম রিপোর্ট',
    tile_classroom_sub:  'এসি · প্রজেক্টর · নেট',
    tile_feed:           'সংবাদ প্রকাশ',
    tile_feed_sub_campus: 'নোটিশ ও গুজব',
    tile_rate:           'বিভাগ রেট করুন',
    tile_rate_sub:       'SWE · CSE · BBA',

    // ── Home tiles · National ─────────────────────────────────
    tile_fir:            'এফআইআর / জিডি খসড়া',
    tile_fir_sub:        'এআই-সহায়ক নথি',
    tile_lawyer:         'আইনজীবী খুঁজুন',
    tile_lawyer_sub:     'এন্ড-টু-এন্ড এনক্রিপ্টেড',
    tile_zones:          'রেড জোন মানচিত্র',
    tile_zones_sub:      'ঢাকা · লাইভ ওভারলে',
    tile_rights:         'আপনার অধিকার জানুন',
    tile_rights_sub:     'দণ্ডবিধি · ডিভি আইন',
    tile_feed_sub_national: 'মানব-নিয়ন্ত্রিত',
    tile_officer:        'অফিসার স্কোরকার্ড',
    tile_officer_sub:    'জনস্বচ্ছতা',

    // ── Profile / Settings groups ─────────────────────────────
    set_group_legal:         'আইনি',
    set_group_prefs:         'পছন্দসমূহ',
    set_group_safety:        'নিরাপত্তা',
    set_group_data:          'ডেটা',
    set_group_location:      'অবস্থান',
    set_group_notifications: 'বিজ্ঞপ্তি',
    set_messages:        'বার্তা',
    set_messages_val:    'এনক্রিপ্টেড',
    set_apply_lawyer:    'আইনজীবী হিসেবে আবেদন',
    set_my_lawyer:       'আমার আইনজীবী প্রোফাইল',
    set_lawyer_verified: 'যাচাইকৃত',
    set_lawyer_pending:  'যাচাই',
    set_language:        'ভাষা',
    set_notifications:   'বিজ্ঞপ্তি',
    set_anonymity:       'ডিফল্ট নামহীনতা',
    set_anonymity_val:   'সবসময় জিজ্ঞাসা',
    set_dms:             'ডেড ম্যান’স সুইচ',
    set_2fa:             'দ্বি-স্তর প্রমাণীকরণ',
    set_2fa_off:         'সেট আপ করা হয়নি',
    set_contacts:        'বিশ্বস্ত যোগাযোগ',
    set_export:          'আমার ডেটা রপ্তানি',
    set_delete:          'অ্যাকাউন্ট মুছুন',
    set_delete_val:      'স্থায়ী',
    set_nearby_alerts:   'কাছাকাছি সতর্কতা',
    set_safety_notif:    'নিরাপত্তা সতর্কতা বিজ্ঞপ্তি',
    set_group_appearance: 'অ্যাপিয়ারেন্স',
    set_dark_mode:        'ডার্ক মোড',
    set_dark_mode_on:     'চালু — রাতে চোখের জন্য আরামদায়ক',
    set_dark_mode_off:    'বন্ধ — হালকা থিম চলছে',

    // ── Language picker card ──────────────────────────────────
    lang_title:          'ভাষা',
    lang_question:       'অ্যাঙ্কর আপনার সাথে কীভাবে কথা বলবে?',
    lang_switch_anytime: 'যেকোনো সময় পরিবর্তন · আমরা দুটোই বুঝি',
  };

  function normLang(lang) {
    var l = String(lang || '').toUpperCase();
    return (l === 'BN' || l === 'BI') ? l : 'EN';
  }

  // Resolve a key for the active language.
  //   BN  → Bangla for everything.
  //   BI  → Bangla only for type='content'; English UI chrome.
  //   EN  → English.
  // Falls back to English, then to the raw key. Never blank, never throws.
  window.tStr = function (key, lang, type) {
    try {
      var l = normLang(lang);
      var useBangla = (l === 'BN') || (l === 'BI' && type === 'content');
      var dict = useBangla ? BN : EN;
      var val = dict[key];
      if (val === undefined || val === null || val === '') val = EN[key];
      return (val === undefined || val === null) ? key : val;
    } catch (e) {
      return key;
    }
  };

  // Normalize any language value to a content language ('EN' | 'BN').
  // Used by chat/routine where "Both" must render content in Bangla and where
  // the value is forwarded to the backend (which only knows EN/BN).
  window.contentLang = function (lang) {
    var l = normLang(lang);
    return (l === 'BN' || l === 'BI') ? 'BN' : 'EN';
  };

  window.ANCHOR_STRINGS = { en: EN, bn: BN };
})();
