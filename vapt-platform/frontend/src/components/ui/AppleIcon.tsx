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
  | "file-up"
  | "edit"
  | "question"
  | "arrow-uturn-clockwise"
  | "rect-2-stack"
  | "rect-3-stack"
  | "sun"
  | "refresh"
  | "unlock"
  | "circle-dot"
  | "wifi-off"
  | "arrow-down"
  | "arrow-up"
  | "arrow-up-right"
  | "more-vertical"
  | "circle-exclamation"
  | "clipboard-list"
  | "workflow"
  | "shield-bang"
  | "users-2"
  | "refresh-cw"
  | "envelope-bang-stroke"
  | "file-down-stroke"
  | "file-up-stroke";

const PATHS: Record<AppleIconName, string> = {
  "shield": "M12 2l8 4v6c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-4z",
  "shield-fill": "M12 2l8 4v6c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-4z",
  "shield-check": "M12 2l8 4v6c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-4zM9 12l2 2 4-4",
  "shield-exclamation": "M12 2l8 4v6c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-4zM12 8v4M12 16h.01",
  "shield-keyhole": "M12 2l8 4v6c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-4zM12 9a2 2 0 1 0 0 4 2 2 0 0 0 0-4z",
  "shield-cross": "M12 2l8 4v6c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-4zM9 11h6",
  "shield-off": "M5 5l14 14M12 2l8 4v6c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-4z",
  "shield-bang": "M12 2l8 4v6c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-4zM12 8v4M11 16h2v-2h-2v2h2",
  "grid": "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  "doc": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6",
  "doc-text": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6zM8 13h8M8 17h5",
  "table": "M3 3h18v18H3zM3 9h18M9 3v18M15 3v18",
  "eye": "M1 12s4-8 11-8 11 8 4-8 11-8-11-8-11 8zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  "magnifier": "M11 3a8 8 0 1 1 0 16 8 8 0 0 1 0-16zM21 21l-4-4",
  "chevron-left": "M15 18l-6-6 6-6",
  "chevron-right": "M9 6l6 6-6 6",
  "chevron-up": "M6 15l6-6 6 6",
  "chevron-down": "M6 9l6 6 6-6",
  "list-bullet": "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  "columns": "M3 3h18v18H3zM9 3v18M15 3v18",
  "tag": "M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82zM7 7h.01",
  "tag-fill": "M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z",
  "person": "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  "person-2": "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM16 7a4 4 0 1 0-8 0 4 4 0 0 0 8 0z",
  "person-3": "M16 21v-2a4 4 0 0 0-4-4h-2M9 21v-2a4 4 0 0 0-4 4V5a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v10zM16 7a4 4 0 1 0-8 0 4 4 0 0 0 8 0z",
  "circle-stack": "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM12 9a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM12 14a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  "logout": "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  "gear": "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.12a2 2 0 0 1-2.83 2.83l-.12.06a1.65 1.65 0 0 0-1.82.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82-.33l-.12.06a2 2 0 0 1-2.83-2.83l.06-.12A1.65 1.65 0 0 0 19.4 15zM9 12a3 3 0 1 0 6 0 3 3 0 0 0-6 0z",
  "moon": "M21 12.79A9 9 0 1 1 11.21 3 7.5 7.5 0 0 0 21 12.79z",
  "bell": "M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0",
  "broom": "M19.36 2.72l1.42 1.42-7.07 7.07 3.54-3.54M5 12.5L1.94 9.43l3.54-3.54L9.43 1.94 1.06-1.06L2.83 2.83 1.06 1.06-3.54 3.54 1.06 1.06 1.42 1.42-1.06 1.06 3.54 3.54 1.06 1.06 1.42 1.42 3.54-3.54 1.42-1.42L19.36 2.72zM14.95 13.95l3.54 3.54-1.06 1.06-3.54-3.54 1.06-1.06 3.54-3.54 1.06-1.06-3.54-3.54 1.06-1.06 3.54 3.54-1.06 1.06z",
  "flask": "M9 3v6L4 19a2 2 0 0 0 2 3h12a2 2 0 0 0 2-3l-5-10V3M9 3h6",
  "envelope": "M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM22 6l-10 7L2 6",
  "envelope-open": "M21 8v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8l9 5 9-5zM3 6l9 6 9-6",
  "envelope-bang": "M21 8v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8l9 5 9-5zM3 6l9 6 9-6M19 14h.01",
  "envelope-bang-stroke": "M21 8v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8l9 5 9-5zM3 6l9 6 9-6M19 14h.01",
  "link": "M10 13a5 5 0 0 0 7.07.07l1.41 1.41a1 1 0 0 1 0 1.41l-1.42 1.42a3 3 0 0 1-4.24 0l-1.42-1.42a5 5 0 0 1 0-7.07l1.42-1.42a1 1 0 0 1 1.41 0l1.42-1.41a3 3 0 0 1 4.24 0l1.42 1.42a1 1 0 0 1 0 1.41z",
  "circle": "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z",
  "circle-dot": "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10z",
  "check": "M5 13l4 4L19 7",
  "check-shield": "M12 2l8 4v6c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-4zM9 12l2 2 4-4",
  "plus": "M12 5v14M5 12h14",
  "x-mark": "M18 6L6 18M6 6l12 12",
  "trash": "M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2z",
  "bolt": "M13 2L3 14h9l-1 8 10-12H12l1-8z",
  "exclamation": "M12 9v4M12 17h.01M3 6h18L12 22z",
  "exclamation-triangle": "M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3H16.47a2 2 0 0 0 1.71-3L9.71 3.86a2 2 0 0 0-1.42 0zM12 9v4M12 17h.01",
  "pencil": "M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 4 1 1 4-4 11.5-12.5a2.1 2.1 0 0 1 3-3z",
  "at-symbol": "M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-4 8M4 13a8 8 0 0 0 16 13",
  "message": "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2zM3 7v10l4-4h10l4 4z",
  "globe": "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM2 12h20",
  "arrow-left-right": "M17 11l-4-4 4-4M7 13l4 4-4-4M17 11h6M7 13H1",
  "arrow-uturn": "M3 12a9 9 0 1 0 18 0L21 12M21 12v7h-7M3 12V5h7",
  "rect-grid": "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  "rect-list": "M3 5h18v2H3zM3 11h18v2H3zM3 17h18v2H3z",
  "rect-column": "M3 5h5v14H3zM10 5h5v14h-5zM17 5h5v14h-5z",
  "wifi": "M5 12.55a11 11 0 0 1 14.08 0M1.42 9a16 16 0 0 1 21.16 0M8.53 15.4a6 6 0 0 1 6.95 0M12 20h.01",
  "wifi-off": "M1 1l22 22M5 12.55a10.94 10.94 0 0 1 3.77 1.36l1.42 1.42A11 11 0 0 0 5 12.55zM16.42 17.04a6 6 0 0 1-5.66 0l1.42-1.42a4 4 0 0 0-5.66 0zM12 20h.01",
  "chart-bar": "M3 3h18v18H3zM7 16v-5M12 16v-9M17 16v-3",
  "sparkles": "M12 2l1.5 4.5L18 8l-4.5 1.5L12 14l-1.5-4.5L6 8l4.5-1.5zM5 17l1 3 3 1-1 3-3-1-1-3zM19 17l1 3 3 1-1 3-3-1-1-3z",
  "circle-check": "M9 12l2 2 4-4M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z",
  "circle-exclamation": "M9 12l2 2 4-4M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM12 8v4",
  "server": "M3 5h18v14H3zM3 9h18M7 5v14M11 5v14M15 5v14M19 5v14",
  "box-archive": "M3 3h18v18H3zM7 7h14v2H7zM7 11h14v2H7zM7 15h14v2H7z",
  "users": "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-4-4h-2M17 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  "users-2": "M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM16 7a4 4 0 1 0-8 0 4 4 0 0 0 8 0zM23 21v-2a4 4 0 0 0-4-4h-2M17 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  "user": "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  "cloud": "M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z",
  "building": "M3 21V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v16M9 9h6M9 13h6M15 9h6M15 13h6",
  "smartphone": "M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zM12 18h.01",
  "package": "M21 8L12 3 3 8v8l9 5 9-5V8zM3.5 7.5L12 12.5l8.5-5M12 12.5V21.5",
  "calendar": "M3 6h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM3 10h18",
  "clock": "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM12 6v6l4 2",
  "lock": "M5 11h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2zM8 11V7a4 4 0 1 1 8 0v4",
  "lock-open": "M5 11h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2zM8 11V7a4 4 0 1 1 8 0",
  "unlock": "M5 11h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2zM8 11V7a4 4 0 1 1 8 0M3 7V3h14v4",
  "key": "M21 2l-2 2m-7.61 7.61a5.5 5.5 0 0 0-7.78 0L7.78 11.39a5.5 5.5 0 0 0 0 7.78zM15.5 7.5l-3 3",
  "play": "M6 4l13 8-13 8V4z",
  "download": "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M7 15h10",
  "upload": "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M17 15H7",
  "save": "M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2zM17 21v-8H7v8M7 3v5h8",
  "print": "M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H6M6 14h12v8H6z",
  "copy": "M20 9h-9a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2v-9a2 2 0 0 0-2-2zM5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1",
  "send": "M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z",
  "wrench": "M14.7 6.3a4 4 0 0 0-5.4 5.4l-7 7 3 3 7-7a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.5-2.5 2-2z",
  "filter": "M22 3H2l8 9.5V19l4 2v-8.5L22 3z",
  "radar": "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM12 6a6 6 0 1 0 0 12 6 6 0 0 0 0-12zM12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4z",
  "zap": "M13 2L3 14h9l-1 8 10-12H12l1-8z",
  "plug": "M9 2v6M15 2v6M6 8h12v3a6 6 0 0 1-12 0V8zM12 17v5",
  "bot": "M12 8V5a3 3 0 0 1 6 0v3M5 8h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2zM8 14h.01M16 14h.01",
  "trending-up": "M23 6l-9.5 9.5-5-5L1 18M17 6h6v6",
  "activity": "M22 12h-4l-3 9-6-18-3 9H2",
  "bug": "M20 7h-3V5a2 2 0 0 0-2-2H9a2 2 0 0 0-2 2v2H4M3 13h18M5 7l-2-2M19 7l2-2M5 17l-2 2M19 17l2 2M9 13v8M15 13v8M12 13v8",
  "file-input": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zM14 2v6h6M12 18v-6M9 15l3 3 3-3",
  "file-down": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zM14 2v6h6M12 18l-4-4h8z",
  "file-down-stroke": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zM14 2v6h6M12 18l-4-4h8z",
  "file-up": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zM14 2v6h6M12 10l-4 4h8z",
  "file-up-stroke": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zM14 2v6h6M12 10l-4 4h8z",
  "edit": "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z",
  "question": "M9 9a3 3 0 1 1 5 2c-1 1-2 1.5-2 3M12 17h.01M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z",
  "arrow-uturn-clockwise": "M3 12a9 9 0 1 0 18 0L21 12M21 12v7h-7M3 12V5h7M9 9l-3 3 3-3",
  "rect-2-stack": "M3 7h18v13H3zM3 7l9 6 9-6M3 18l9 5 9-5",
  "rect-3-stack": "M3 7h18v4H3zM3 11h18M3 15h18v4H3zM3 19h18",
  "sun": "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42",
  "refresh": "M3 12a9 9 0 1 0 9-9 9.74 9.74 0 0 0-6.74 2.74L3 8M3 3v5h5",
  "refresh-cw": "M3 12a9 9 0 1 0 9-9 9.74 9.74 0 0 0-6.74 2.74L3 8M3 3v5h5",
  "arrow-down": "M12 5v14M5 12l7 7 7-7",
  "arrow-up": "M12 19V5M5 12l7-7 7 7",
  "arrow-up-right": "M7 17L17 7M7 7h10v10",
  "more-vertical": "M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM12 6a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM12 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2z",
  "clipboard-list": "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v0a2 2 0 0 1-2 2h-2a2 2 0 0 1-2-2zM9 12h6M9 16h4M12 8h.01",
  "workflow": "M5 4h4v4H5zM5 12h4v4H5zM11 4h4v4h-4zM11 12h4v4h-4zM17 4h4v4h-4zM17 12h4v4h-4zM3 4h18v16H3z",
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
