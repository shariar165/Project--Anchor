// Demo data for the Anchor AI admin panel.
//
// NOTE: dashboards, complaints, alerts, audit trail, and system health now load LIVE
// from the backend (see uni-dashboard.jsx, super.jsx). The only remaining mock below is
// the routine-builder sample, still used by uni-routine.jsx until the timetable UI is
// wired to /v1/admin/timetable. Tenants load live from /v1/super-admin/tenants.
window.AnchorData = (() => {
  // Routine builder sample timetable (Sun-Thu, 8 slots)
  const days = ['Sun','Mon','Tue','Wed','Thu'];
  const slots = ['08:00','09:30','11:00','12:30','14:00','15:30','17:00','18:30'];
  // section color map
  const sectionColors = {
    '54-A': '#4A6B5C',
    '54-B': '#B8893A',
    '53-A': '#13294B',
    '53-B': '#C44536',
    '55-A': '#3A4754',
  };
  // build sample entries
  const timetable = [
    { d:0, s:0, code:'SWE-301', sec:'54-A', room:'KT-504', teacher:'Mahbub A.' },
    { d:0, s:1, code:'SWE-405', sec:'54-A', room:'KT-308', teacher:'Tahmina K.' },
    { d:0, s:3, code:'SWE-201', sec:'55-A', room:'AB1-201', teacher:'Farzana R.' },
    { d:1, s:0, code:'SWE-405', sec:'54-B', room:'KT-712', teacher:'Tahmina K.' },
    { d:1, s:2, code:'SWE-301', sec:'53-A', room:'KT-504', teacher:'Mahbub A.' },
    { d:1, s:4, code:'SWE-410', sec:'53-B', room:'AB2-105', teacher:'Imran C.' },
    { d:2, s:1, code:'SWE-201', sec:'55-A', room:'KT-401', teacher:'Farzana R.' },
    { d:2, s:3, code:'SWE-405', sec:'54-A', room:'KT-308', teacher:'Tahmina K.', conflict: true },
    { d:2, s:5, code:'SWE-410', sec:'53-A', room:'AB2-105', teacher:'Imran C.' },
    { d:3, s:0, code:'SWE-301', sec:'54-B', room:'KT-504', teacher:'Mahbub A.' },
    { d:3, s:2, code:'SWE-410', sec:'53-B', room:'AB2-105', teacher:'Imran C.' },
    { d:3, s:4, code:'SWE-201', sec:'55-A', room:'AB1-201', teacher:'Farzana R.' },
    { d:4, s:1, code:'SWE-405', sec:'54-B', room:'KT-712', teacher:'Tahmina K.' },
    { d:4, s:3, code:'SWE-301', sec:'53-A', room:'KT-504', teacher:'Mahbub A.' },
  ];

  const courses = [
    { code:'SWE-201', name:'Object Oriented Programming', credits:3, type:'Theory', sections:2, teacher:'Dr. Farzana Rahman' },
    { code:'SWE-301', name:'Algorithms', credits:3, type:'Theory', sections:3, teacher:'Dr. Mahbub Alam' },
    { code:'SWE-405', name:'Software Architecture Lab', credits:1, type:'Lab', sections:3, teacher:'Dr. Tahmina Karim' },
    { code:'SWE-410', name:'Distributed Systems', credits:3, type:'Theory', sections:2, teacher:'Dr. Imran Chowdhury' },
  ];

  return { days, slots, timetable, sectionColors, courses };
})();
