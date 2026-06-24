// Anchor — inline SVG icons (Lucide-flavored, hand-tuned)
// All icons accept { size = 18, stroke = 'currentColor', strokeWidth = 1.6, fill = 'none' }

const Ic = ({ d, size = 18, stroke = 'currentColor', sw = 1.6, fill = 'none', children, viewBox = '0 0 24 24' }) => (
  <svg width={size} height={size} viewBox={viewBox} fill={fill} stroke={stroke}
    strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {d ? <path d={d}/> : children}
  </svg>
);

const IconAnchor = (p) => <Ic {...p}>
  <circle cx="12" cy="5" r="2"/>
  <path d="M12 7v15"/>
  <path d="M5 12h14"/>
  <path d="M3 16a9 9 0 0 0 18 0"/>
</Ic>;

const IconMessage = (p) => <Ic {...p}>
  <path d="M21 12a8 8 0 0 1-11.4 7.3L4 21l1.7-5.6A8 8 0 1 1 21 12z"/>
</Ic>;

const IconHome = (p) => <Ic {...p}>
  <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>
</Ic>;

const IconFile = (p) => <Ic {...p}>
  <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>
  <path d="M14 3v5h5"/>
  <path d="M9 13h6M9 17h4"/>
</Ic>;

const IconShield = (p) => <Ic {...p}>
  <path d="M12 2 4 5v6c0 5 3.5 9.5 8 11 4.5-1.5 8-6 8-11V5z"/>
  <path d="M12 8v5"/>
  <circle cx="12" cy="16" r="0.8" fill="currentColor"/>
</Ic>;

const IconUser = (p) => <Ic {...p}>
  <circle cx="12" cy="8" r="4"/>
  <path d="M4 21a8 8 0 0 1 16 0"/>
</Ic>;

const IconBell = (p) => <Ic {...p}>
  <path d="M6 8a6 6 0 1 1 12 0c0 7 3 7 3 9H3c0-2 3-2 3-9z"/>
  <path d="M10 21a2 2 0 0 0 4 0"/>
</Ic>;

const IconMic = (p) => <Ic {...p}>
  <rect x="9" y="3" width="6" height="11" rx="3"/>
  <path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>
</Ic>;

const IconImage = (p) => <Ic {...p}>
  <rect x="3" y="4" width="18" height="16" rx="2"/>
  <circle cx="9" cy="10" r="1.6"/>
  <path d="m4 18 5-5 4 4 3-3 4 4"/>
</Ic>;

const IconSearch = (p) => <Ic {...p}>
  <circle cx="11" cy="11" r="7"/>
  <path d="m20 20-4-4"/>
</Ic>;

const IconArrowLeft = (p) => <Ic {...p}>
  <path d="M19 12H5M12 5l-7 7 7 7"/>
</Ic>;

const IconArrowRight = (p) => <Ic {...p}>
  <path d="M5 12h14M12 5l7 7-7 7"/>
</Ic>;

const IconArrowUp = (p) => <Ic {...p}>
  <path d="M12 19V5M5 12l7-7 7 7"/>
</Ic>;

const IconCheck = (p) => <Ic {...p}>
  <path d="m5 12 5 5L20 7"/>
</Ic>;

const IconX = (p) => <Ic {...p}>
  <path d="M18 6 6 18M6 6l12 12"/>
</Ic>;

const IconMap = (p) => <Ic {...p}>
  <path d="m9 4-6 2v14l6-2 6 2 6-2V4l-6 2z"/>
  <path d="M9 4v16M15 6v16"/>
</Ic>;

const IconGavel = (p) => <Ic {...p}>
  <path d="m14 4 6 6-3 3-6-6z"/>
  <path d="m9 9 6 6-4 4-6-6z"/>
  <path d="M3 21h10"/>
</Ic>;

const IconBook = (p) => <Ic {...p}>
  <path d="M4 4h10a4 4 0 0 1 4 4v12H8a4 4 0 0 1-4-4z"/>
  <path d="M4 16a4 4 0 0 1 4-4h10"/>
</Ic>;

const IconBuilding = (p) => <Ic {...p}>
  <rect x="4" y="3" width="16" height="18" rx="1"/>
  <path d="M8 7h2M14 7h2M8 11h2M14 11h2M8 15h2M14 15h2"/>
  <path d="M10 21v-3h4v3"/>
</Ic>;

const IconBed = (p) => <Ic {...p}>
  <path d="M3 20V8M3 14h18v6M21 14V9a2 2 0 0 0-2-2h-9v7"/>
  <circle cx="7.5" cy="11.5" r="1.5"/>
</Ic>;

const IconStar = (p) => <Ic {...p}>
  <path d="m12 3 2.7 5.7L21 9.6l-4.5 4.3L17.6 21 12 17.8 6.4 21l1.1-7.1L3 9.6l6.3-.9z"/>
</Ic>;

const IconClock = (p) => <Ic {...p}>
  <circle cx="12" cy="12" r="9"/>
  <path d="M12 7v5l3 2"/>
</Ic>;

const IconLock = (p) => <Ic {...p}>
  <rect x="4" y="11" width="16" height="10" rx="2"/>
  <path d="M8 11V7a4 4 0 0 1 8 0v4"/>
</Ic>;

const IconEyeOff = (p) => <Ic {...p}>
  <path d="M3 3l18 18"/>
  <path d="M10.5 6.3A9.7 9.7 0 0 1 12 6c5 0 9 4 10 6-0.4 0.9-1.4 2.5-3 4"/>
  <path d="M6.6 6.6C4 8 2.4 10.3 2 12c1 2 5 6 10 6 1.8 0 3.4-.5 4.7-1.3"/>
  <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>
</Ic>;

const IconPlus = (p) => <Ic {...p}>
  <path d="M12 5v14M5 12h14"/>
</Ic>;

const IconAlert = (p) => <Ic {...p}>
  <path d="M12 3 1 21h22z"/>
  <path d="M12 10v4"/>
  <circle cx="12" cy="17.5" r="0.8" fill="currentColor"/>
</Ic>;

const IconChevronRight = (p) => <Ic {...p}>
  <path d="m9 6 6 6-6 6"/>
</Ic>;

const IconScale = (p) => <Ic {...p}>
  <path d="M12 3v18M5 7h14"/>
  <path d="m5 7-2 6a3 3 0 0 0 6 0z"/>
  <path d="m19 7-2 6a3 3 0 0 0 6 0z"/>
  <path d="M8 21h8"/>
</Ic>;

const IconNews = (p) => <Ic {...p}>
  <rect x="3" y="4" width="14" height="16" rx="1"/>
  <path d="M17 8h4v10a2 2 0 0 1-2 2h-2"/>
  <path d="M7 8h6M7 12h6M7 16h4"/>
</Ic>;

const IconBadge = (p) => <Ic {...p}>
  <path d="M12 2l2 3 3-1 0 3 3 2-2 3 2 3-3 2 0 3-3-1-2 3-2-3-3 1 0-3-3-2 2-3-2-3 3-2 0-3 3 1z"/>
</Ic>;

const IconGlobe = (p) => <Ic {...p}>
  <circle cx="12" cy="12" r="9"/>
  <path d="M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18z"/>
</Ic>;

const IconUpload = (p) => <Ic {...p}>
  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
  <path d="M17 8l-5-5-5 5"/>
  <path d="M12 3v12"/>
</Ic>;

const IconSparkles = (p) => <Ic {...p}>
  <path d="M12 3v4M12 17v4M3 12h4M17 12h4"/>
  <path d="m6 6 2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>
</Ic>;

const IconChat = (p) => <Ic {...p}>
  <path d="M3 5h18v12H7l-4 4z"/>
  <path d="M8 10h8M8 13h5"/>
</Ic>;

const IconSettings = (p) => <Ic {...p}>
  <circle cx="12" cy="12" r="3"/>
  <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>
</Ic>;

const IconPhone = (p) => <Ic {...p}>
  <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3-8.6A2 2 0 0 1 4.2 2h3a2 2 0 0 1 2 1.7c.1.9.3 1.8.6 2.6a2 2 0 0 1-.5 2.1L8 9.7a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.5c.8.3 1.7.5 2.6.6a2 2 0 0 1 1.7 2z"/>
</Ic>;

const IconHeart = (p) => <Ic {...p}>
  <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.8 1-1a5.5 5.5 0 0 0 0-7.6z"/>
</Ic>;

const IconRoute = (p) => <Ic {...p}>
  <circle cx="6" cy="19" r="3"/>
  <circle cx="18" cy="5" r="3"/>
  <path d="M6 16V10a4 4 0 0 1 4-4h4a4 4 0 0 1 4-4"/>
</Ic>;

const IconLink = (p) => <Ic {...p}>
  <path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/>
  <path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>
</Ic>;

const IconCamera = (p) => <Ic {...p}>
  <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
  <circle cx="12" cy="13" r="4"/>
</Ic>;

const IconMore = (p) => <Ic {...p}>
  <circle cx="12" cy="6" r="1" fill="currentColor"/>
  <circle cx="12" cy="12" r="1" fill="currentColor"/>
  <circle cx="12" cy="18" r="1" fill="currentColor"/>
</Ic>;

const IconThumbUp = (p) => <Ic {...p}>
  <path d="M7 22V11M2 13v7a2 2 0 0 0 2 2h13.3a2 2 0 0 0 2-1.7l1.4-7A2 2 0 0 0 18.7 11H13l1-5a2.5 2.5 0 0 0-5-1L7 11"/>
</Ic>;

const IconThumbDown = (p) => <Ic {...p}>
  <path d="M17 2v11M22 11V4a2 2 0 0 0-2-2H6.7a2 2 0 0 0-2 1.7l-1.4 7A2 2 0 0 0 5.3 13H11l-1 5a2.5 2.5 0 0 0 5 1l2-6"/>
</Ic>;

const IconDoc = (p) => <Ic {...p}>
  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
  <path d="M14 2v6h6"/>
  <path d="M9 13h6M9 17h4"/>
  <circle cx="9" cy="9" r="0.8" fill="currentColor"/>
</Ic>;

const IconSend = (p) => <Ic {...p}>
  <path d="M22 2 11 13"/>
  <path d="M22 2 15 22 11 13 2 9z"/>
</Ic>;

const IconPaperclip = (p) => <Ic {...p}>
  <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 0 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
</Ic>;

const IconDownload = (p) => <Ic {...p}>
  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
  <path d="m7 10 5 5 5-5"/>
  <path d="M12 15V3"/>
</Ic>;

const IconMoon = (p) => <Ic {...p}>
  <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>
</Ic>;

const IconSun = (p) => <Ic {...p}>
  <circle cx="12" cy="12" r="4"/>
  <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>
</Ic>;

Object.assign(window, {
  IconAnchor, IconMessage, IconHome, IconFile, IconShield, IconUser, IconBell,
  IconMic, IconImage, IconSearch, IconArrowLeft, IconArrowRight, IconArrowUp,
  IconCheck, IconX, IconMap, IconGavel, IconBook, IconBuilding, IconBed,
  IconStar, IconClock, IconLock, IconEyeOff, IconPlus, IconAlert, IconChevronRight,
  IconScale, IconNews, IconBadge, IconGlobe, IconUpload, IconSparkles, IconChat,
  IconSettings, IconPhone, IconHeart, IconRoute, IconLink, IconCamera, IconMore,
  IconThumbUp, IconThumbDown, IconDoc, IconSend, IconPaperclip, IconDownload,
  IconMoon, IconSun,
});
