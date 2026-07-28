import { cn } from "../../lib/cn";

export type AppleIconName =
  | "shield"
  | "shield-fill"
  | "shield-check"
  | "shield-exclamation"
  | "shield-keyhole"
  | "shield-cross"
  | "shield-off"
  | "grid"
  | "doc"
  | "doc-text"
  | "table"
  | "eye"
  | "magnifier"
  | "chevron-left"
  | "chevron-right"
  | "chevron-up"
  | "chevron-down"
  | "list-bullet"
  | "columns"
  | "tag"
  | "tag-fill"
  | "person"
  | "person-2"
  | "person-3"
  | "circle-stack"
  | "logout"
  | "gear"
  | "moon"
  | "bell"
  | "broom"
  | "flask"
  | "envelope"
  | "envelope-open"
  | "envelope-bang"
  | "link"
  | "circle"
  | "check"
  | "check-shield"
  | "plus"
  | "x-mark"
  | "trash"
  | "bolt"
  | "exclamation"
  | "exclamation-triangle"
  | "pencil"
  | "at-symbol"
  | "message"
  | "globe"
  | "arrow-left-right"
  | "arrow-uturn"
  | "rect-grid"
  | "rect-list"
  | "rect-column"
  | "wifi"
  | "chart-bar"
  | "sparkles"
  | "circle-check"
  | "server"
  | "box-archive"
  | "users"
  | "user"
  | "cloud"
  | "building"
  | "smartphone"
  | "package"
  | "calendar"
  | "clock"
  | "lock"
  | "lock-open"
  | "key"
  | "play"
  | "download"
  | "upload"
  | "save"
  | "print"
  | "copy"
  | "send"
  | "wrench"
  | "filter"
  | "radar"
  | "zap"
  | "plug"
  | "bot"
  | "trending-up"
  | "activity"
  | "bug"
  | "file-input"
  | "file-down"
  | "edit"
  | "question"
  | "arrow-uturn-clockwise"
  | "rect-2-stack"
  | "rect-3-stack";

const PATHS: Record<AppleIconName, string> = {
  "shield": "M12 2.5l7.5 3.5v5.5c0 4.8-3.2 8.4-7.5 10-4.3-1.6-7.5-5.2-7.5-10V6L12 2.5z",
  "shield-fill": "M12 2.5l7.5 3.5v5.5c0 4.8-3.2 8.4-7.5 10-4.3-1.6-7.5-5.2-7.5-10V6L12 2.5z",
  "shield-check": "M12 2.5l7.5 3.5v5.5c0 4.8-3.2 8.4-7.5 10-4.3-1.6-7.5-5.2-7.5-10V6L12 2.5zM8.5 12l2.5 2.5 4.5-4.5",
  "shield-exclamation": "M12 2.5l7.5 3.5v5.5c0 4.8-3.2 8.4-7.5 10-4.3-1.6-7.5-5.2-7.5-10V6L12 2.5zM12 8v5M12 16h.01",
  "shield-keyhole": "M12 2.5l7.5 3.5v5.5c0 4.8-3.2 8.4-7.5 10-4.3-1.6-7.5-5.2-7.5-10V6L12 2.5zM12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4z",
  "shield-cross": "M12 2.5l7.5 3.5v5.5c0 4.8-3.2 8.4-7.5 10-4.3-1.6-7.5-5.2-7.5-10V6L12 2.5zM9 12h6",
  "shield-off": "M12 2.5l7.5 3.5v5.5c0 4.8-3.2 8.4-7.5 10-4.3-1.6-7.5-5.2-7.5-10V6L12 2.5zM3 3l18 18",
  "grid": "M3 3h7.5v7.5H3zM13.5 3H21v7.5h-7.5zM3 13.5h7.5V21H3zM13.5 13.5H21V21h-7.5z",
  "doc": "M14 2.5H6a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8.5L14 2.5zM14 2.5V8.5h6",
  "doc-text": "M14 2.5H6a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8.5L14 2.5zM14 2.5V8.5h6M8 13h8M8 17h5",
  "table": "M3 4.5h18v15H3zM3 9.5h18M9 4.5v15M15 4.5v15",
  "eye": "M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  "magnifier": "M11 3.5a7.5 7.5 0 1 1 0 15 7.5 7.5 0 0 1 0-15zM21 20.5l-4.5-4.5",
  "chevron-left": "M14.5 5.5l-6 6.5 6 6.5",
  "chevron-right": "M9.5 5.5l6 6.5-6 6.5",
  "chevron-up": "M5.5 14.5l6.5-6 6.5 6",
  "chevron-down": "M5.5 9.5l6.5 6 6.5-6",
  "list-bullet": "M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01",
  "columns": "M3 4.5h18v15H3zM9 4.5v15M15 4.5v15",
  "tag": "M20.5 12.5L13 20a1.5 1.5 0 0 1-2.1 0L3 12.1V3h9.1l7.9 7.9a1.5 1.5 0 0 1 0 2.1zM7 7.5h.01",
  "tag-fill": "M20.5 12.5L13 20a1.5 1.5 0 0 1-2.1 0L3 12.1V3h9.1l7.9 7.9a1.5 1.5 0 0 1 0 2.1z",
  "person": "M20 20.5v-1.5a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v1.5M12 11.5a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  "person-2": "M20 20.5v-1.5a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v1.5M16 7.5a4 4 0 1 1-8 0 4 4 0 0 1 8 0z",
  "person-3": "M17 20.5v-1.5a4 4 0 0 0-3-3.9M9 15.1a4 4 0 0 0-3 3.9v1.5M9 11.5a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM16 7.5a4 4 0 1 0 0-4",
  "circle-stack": "M3 12a9 9 0 1 1 18 0 9 9 0 0 1-18 0zM12 7.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zM3 18a9 9 0 1 0 18 0 9 9 0 0 0-18 0z",
  "logout": "M9 20.5H5a2 2 0 0 1-2-2V5.5a2 2 0 0 1 2-2h4M15.5 16.5l5-4.5-5-4.5M20.5 12H9",
  "gear": "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 14.5a1.6 1.6 0 0 0 .3 1.7l.1.1a1.8 1.8 0 0 1-2.5 2.5l-.1-.1a1.6 1.6 0 0 0-1.7-.3 1.6 1.6 0 0 0-1 1.4v.2a1.8 1.8 0 1 1-3.6 0v-.1a1.6 1.6 0 0 0-1-1.4 1.6 1.6 0 0 0-1.7.3l-.1.1a1.8 1.8 0 1 1-2.5-2.5l.1-.1a1.6 1.6 0 0 0 .3-1.7 1.6 1.6 0 0 0-1.4-1H3.2a1.8 1.8 0 1 1 0-3.6H3.3a1.6 1.6 0 0 0 1.4-1 1.6 1.6 0 0 0-.3-1.7l-.1-.1a1.8 1.8 0 1 1 2.5-2.5l.1.1a1.6 1.6 0 0 0 1.7.3h.1a1.6 1.6 0 0 0 1-1.4V3.2a1.8 1.8 0 1 1 3.6 0V3.3a1.6 1.6 0 0 0 1 1.4 1.6 1.6 0 0 0 1.7-.3l.1-.1a1.8 1.8 0 1 1 2.5 2.5l-.1.1a1.6 1.6 0 0 0-.3 1.7v.1a1.6 1.6 0 0 0 1.4 1h.2a1.8 1.8 0 1 1 0 3.6h-.1a1.6 1.6 0 0 0-1.4 1z",
  "moon": "M20.5 12.8A8.5 8.5 0 1 1 11.2 3.5a6.8 6.8 0 0 0 9.3 9.3z",
  "bell": "M18 8.5a6 6 0 0 0-12 0c0 6-2.5 7.5-2.5 7.5h17s-2.5-1.5-2.5-7.5M13.7 20.5a1.8 1.8 0 0 1-3.4 0",
  "broom": "M14 3.5l6.5 6.5M5.5 12.5l6 6M9 9l6-6 6 6-6 6-6-6zM3 20.5h18",
  "flask": "M9 3v5.5L4 19a1.5 1.5 0 0 0 1.4 2.3h13.2A1.5 1.5 0 0 0 20 19l-5-10.5V3M9 3h6M7 15h10",
  "envelope": "M3.5 4.5h17a1.5 1.5 0 0 1 1.5 1.5v12a1.5 1.5 0 0 1-1.5 1.5h-17A1.5 1.5 0 0 1 2 18V6a1.5 1.5 0 0 1 1.5-1.5zM22 6.5L12 13 2 6.5",
  "envelope-open": "M21 9v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18V9l9 5 9-5zM3 6.5l9 5 9-5",
  "envelope-bang": "M21 9v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18V9l9 5 9-5zM3 6.5l9 5 9-5M19 14h.01M19 17.5h.01",
  "link": "M9.5 14.5a4 4 0 0 0 5.7 0l3-3a4 4 0 1 0-5.7-5.7l-1 1M14.5 9.5a4 4 0 0 0-5.7 0l-3 3a4 4 0 1 0 5.7 5.7l1-1",
  "circle": "M12 2.5a9.5 9.5 0 1 0 0 19 9.5 9.5 0 0 0 0-19z",
  "check": "M4.5 12.5l4.5 4.5L19.5 6.5",
  "check-shield": "M12 2.5l7.5 3.5v5.5c0 4.8-3.2 8.4-7.5 10-4.3-1.6-7.5-5.2-7.5-10V6L12 2.5zM8.5 12.5l2.5 2.5 4.5-4.5",
  "plus": "M12 5v14M5 12h14",
  "x-mark": "M18 6L6 18M6 6l12 12",
  "trash": "M3.5 6.5h17M8.5 6.5V4.5a1.5 1.5 0 0 1 1.5-1.5h4a1.5 1.5 0 0 1 1.5 1.5v2M18.5 6.5l-1 13a1.5 1.5 0 0 1-1.5 1.4H8a1.5 1.5 0 0 1-1.5-1.4l-1-13",
  "bolt": "M13 2.5L3.5 14h7.5l-1 7.5L19.5 10H12l1-7.5z",
  "exclamation": "M12 7v8M12 18.5h.01",
  "exclamation-triangle": "M12 3.5L2.5 20.5h19L12 3.5zM12 10v5M12 18h.01",
  "pencil": "M16 4l4 4-11 11-4 1 1-4 11-11zM14 6l4 4",
  "at-symbol": "M16 8v5a3.5 3.5 0 0 0 7 0v-1.3A9 9 0 1 0 19 16.5M4.5 13a7.5 7.5 0 0 0 15 0",
  "message": "M21 11.5a1.5 1.5 0 0 1-1.5 1.5h-12L3 17.5V5.5A1.5 1.5 0 0 1 4.5 4h15A1.5 1.5 0 0 1 21 5.5v6z",
  "globe": "M12 2.5a9.5 9.5 0 1 0 0 19 9.5 9.5 0 0 0 0-19zM2.5 12h19M12 2.5a14 14 0 0 1 0 19 14 14 0 0 1 0-19z",
  "arrow-left-right": "M16.5 7.5l4 4-4 4M21 11.5H4.5M7.5 16.5l-4-4 4-4M3 12.5h16.5",
  "arrow-uturn": "M3.5 12a8.5 8.5 0 1 0 17 0V7.5M20.5 3.5v4h-4M3.5 12V4.5h7.5",
  "rect-grid": "M3 3.5h7.5v7.5H3zM13.5 3.5H21v7.5h-7.5zM3 13.5h7.5V21H3zM13.5 13.5H21V21h-7.5z",
  "rect-list": "M3 5.5h18v2H3zM3 11h18v2H3zM3 16.5h18v2H3z",
  "rect-column": "M3 4.5h5.5v15H3zM9.5 4.5H15v15H9.5zM16 4.5h5v15h-5z",
  "wifi": "M5 12.5a10 10 0 0 1 14 0M1.5 9a15 15 0 0 1 21 0M8.5 16a5 5 0 0 1 7 0M12 20.5h.01",
  "chart-bar": "M3 3.5h18v17H3zM7 16v-5M12 16v-9M17 16v-3",
  "sparkles": "M12 2.5l1.8 4.2 4.2 1.8-4.2 1.8-1.8 4.2-1.8-4.2-4.2-1.8 4.2-1.8L12 2.5zM19 14.5l1 2.3 2.3 1-2.3 1-1 2.3-1-2.3-2.3-1 2.3-1L19 14.5zM5 14.5l1 2.3 2.3 1-2.3 1-1 2.3-1-2.3-2.3-1 2.3-1L5 14.5z",
  "circle-check": "M9 12l2 2 4.5-4.5M12 2.5a9.5 9.5 0 1 0 0 19 9.5 9.5 0 0 0 0-19z",
  "server": "M3 5.5h18v13H3zM3 9.5h18M7 5.5v13M11 5.5v13M15 5.5v13M19 5.5v13",
  "box-archive": "M3 3.5h18v17H3zM3 7.5h18M8 12.5h8M10 16.5h4",
  "users": "M16.5 20.5v-1.5a3.5 3.5 0 0 0-3.5-3.5H6a3.5 3.5 0 0 0-3.5 3.5v1.5M9.5 12a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM21.5 20.5v-1.5a3.5 3.5 0 0 0-3-3.5M16 12a3.5 3.5 0 1 0 0-7",
  "user": "M19 20.5v-1.5a3.5 3.5 0 0 0-3.5-3.5h-7A3.5 3.5 0 0 0 5 19v1.5M12 12a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z",
  "cloud": "M17.5 9.5h-1.2A7.5 7.5 0 1 0 9 20.5h8.5a5.5 5.5 0 0 0 0-11z",
  "building": "M3 21V6l9-3 9 3v15M3 21h18M9 9h.01M15 9h.01M9 13h.01M15 13h.01M9 17h.01M15 17h.01",
  "smartphone": "M7 2.5h10a1.5 1.5 0 0 1 1.5 1.5v16a1.5 1.5 0 0 1-1.5 1.5H7A1.5 1.5 0 0 1 5.5 20V4A1.5 1.5 0 0 1 7 2.5zM11 19h2",
  "package": "M21 8L12 3 3 8v8l9 5 9-5V8zM3.5 7.5L12 12.5l8.5-5M12 12.5V21.5",
  "calendar": "M3.5 6.5h17v14h-17zM3.5 10.5h17M8 3.5v4M16 3.5v4M8 14.5h.01M12 14.5h.01M16 14.5h.01M8 18h.01M12 18h.01",
  "clock": "M12 2.5a9.5 9.5 0 1 0 0 19 9.5 9.5 0 0 0 0-19zM12 7v5l3 2",
  "lock": "M5 11.5h14v9.5H5zM8 11.5V7a4 4 0 1 1 8 0v4.5",
  "lock-open": "M5 11.5h14v9.5H5zM8 11.5V7a4 4 0 1 1 8 0",
  "key": "M21 2l-2 2m-7.6 7.6a5 5 0 1 1-7 7 5 5 0 0 1 7-7L19 4l-2 2 2 2-2 2",
  "play": "M6 4.5l13 7.5-13 7.5V4.5z",
  "download": "M12 3.5v12M7 11l5 5 5-5M4.5 19.5h15",
  "upload": "M12 20.5v-12M7 13l5-5 5 5M4.5 19.5h15",
  "save": "M5 3.5h11.5L20 7v12.5a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19.5V5a1.5 1.5 0 0 1 1-1.5zM8 3.5v5h8M8 13.5h8M8 17h5",
  "print": "M6 8.5h12v10H6zM6 8.5V4.5h12v4M6 14.5h-2v-3.5a1.5 1.5 0 0 1 1.5-1.5h13a1.5 1.5 0 0 1 1.5 1.5V14.5h-2",
  "copy": "M9 9.5h11v11H9zM5 15.5h-2v-12h12v2",
  "send": "M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z",
  "wrench": "M14.5 4.5a5 5 0 0 1 6.4 6.4l-2.6-2.6-2.4 2.4 2.6 2.6a5 5 0 0 1-6.4-6.4L3 16.4 7.6 21l9-9z",
  "filter": "M3 4.5h18l-7 9v6.5l-4-2v-4.5l-7-9z",
  "radar": "M12 12.5l9-9M12 12.5a8.5 8.5 0 0 0-12 0M12 12.5a4.5 4.5 0 0 0-6 0M12 12.5a1.5 1.5 0 0 0-2 0",
  "zap": "M4 14.5a8 8 0 0 1 16 0v1M4 15.5h6M14 15.5h6M6 18.5a2 2 0 1 0 4 0 2 2 0 0 0-4 0zM14 18.5a2 2 0 1 0 4 0 2 2 0 0 0-4 0z",
  "plug": "M9 2.5v4M15 2.5v4M7 6.5h10v6a5 5 0 0 1-10 0v-6zM12 17.5v4.5",
  "bot": "M12 7.5v.01M5 7.5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2zM9 7.5V5a3 3 0 0 1 6 0v2.5M8 13h.01M16 13h.01",
  "trending-up": "M3 17l6-6 4 4 8-8M14 7h7v7",
  "activity": "M22 12h-4l-3 9-6-18-3 9H2",
  "bug": "M12 2.5a8 8 0 0 0-8 8v2.5a8 8 0 0 0 16 0V10.5a8 8 0 0 0-8-8zM3 13.5h18M5 7.5l-2.5-2M19 7.5l2.5-2M5 19.5l-2.5 2M19 19.5l2.5 2M12 20.5v-7M9 13.5h6",
  "file-input": "M14 2.5H6a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8.5L14 2.5zM14 2.5V8.5h6M9 13.5h6M9 17h4M12 10.5v6.5M9.5 14l2.5 2.5 2.5-2.5",
  "file-down": "M14 2.5H6a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8.5L14 2.5zM14 2.5V8.5h6M12 11.5v6M9 14.5l3 3 3-3",
  "edit": "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z",
  "question": "M9 9a3 3 0 1 1 4.5 2.6c-1 .5-1.5 1.2-1.5 2.4M12 17h.01M12 21.5a9.5 9.5 0 1 0 0-19 9.5 9.5 0 0 0 0 19z",
  "arrow-uturn-clockwise": "M20.5 8.5v-5h-5M20.5 3.5L16 8a8.5 8.5 0 1 0 2.5 6",
  "rect-2-stack": "M3 6.5h18v11H3zM3 6.5L12 12l9-5.5M3 17.5l9 5.5 9-5.5",
  "rect-3-stack": "M3 3.5h18v5H3zM3 8.5h18M3 13.5h18v5H3zM3 18.5h18",
};

interface AppleIconProps {
  name: AppleIconName;
  size?: number;
  className?: string;
  "aria-label"?: string;
  strokeWidth?: number;
  filled?: boolean;
}

export default function AppleIcon({
  name,
  size = 14,
  className,
  "aria-label": ariaLabel,
  strokeWidth = 1.6,
  filled = false,
}: AppleIconProps) {
  const d = PATHS[name];
  const isFilledVariant = filled || name === "shield-fill" || name === "tag-fill";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={isFilledVariant ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={ariaLabel ? undefined : true}
      aria-label={ariaLabel}
      className={cn("shrink-0", className)}
    >
      <path d={d} />
    </svg>
  );
}
