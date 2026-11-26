import React from "react";
// Decorative, 24-unit outline icons. The containing control supplies the accessible name.
const paths = {
  menu:"M4 6H20 M4 12H16 M4 18H20", close:"M6 6L18 18 M18 6L6 18",
  chat:"M4 4H20V16H10L4 21V4Z", plug:"M8 3V8 M16 3V8 M6 8H18V12A6 6 0 0 1 6 12V8Z M12 18V22",
  user:"M12 3A4 4 0 1 0 12 11A4 4 0 1 0 12 3 M4 21V19A8 8 0 0 1 20 19V21",
  plus:"M12 5V19 M5 12H19",search:"M10.5 3A7.5 7.5 0 1 0 10.5 18A7.5 7.5 0 1 0 10.5 3 M16 16L21 21",
  edit:"M12 4H5A1 1 0 0 0 4 5V19A1 1 0 0 0 5 20H19A1 1 0 0 0 20 19V12 M14 6L18 10 M10 14L11 9L18 2L22 6L15 13L10 14Z",
  sun:"M12 7A5 5 0 1 0 12 17A5 5 0 1 0 12 7 M12 2V4 M12 20V22 M2 12H4 M20 12H22 M5 5L6.5 6.5 M17.5 17.5L19 19 M5 19L6.5 17.5 M17.5 6.5L19 5",
  moon:"M20.5 15.5A9 9 0 0 1 8.5 3.5A9 9 0 1 0 20.5 15.5Z",
  check:"M5 12L10 17L19 7",send:"M12 20V4 M5 11L12 4L19 11",panel:"M3 4H21V20H3Z M9 4V20",
  shield:"M12 3L21 7V12C21 17 17 21 12 23C7 21 3 17 3 12V7Z M8 12L11 15L16 10",
  idea:"M9 18H15 M10 22H14 M8 14C3 8 8 3 12 3S21 8 16 14L15 16H9Z",
  plan:"M4 5H20V20H4Z M8 3V7 M16 3V7 M8 11H16 M8 15H13",
  tasks:"M8 4H5V21H19V4H16 M8 2H16V6H8Z M8 12L10 14L14 10 M8 17H16",
  tools:"M4 4H10V10H4Z M14 4H20V10H14Z M4 14H10V20H4Z M14 14H20V20H14Z"
};
export function UiIcon({name,className="",size=20}) {
  return <svg className={`dz-ui-icon ${className}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false"><path d={paths[name]}/></svg>;
}
