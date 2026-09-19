/**
 * WBR sales dashboard relay.
 * Lives inside the Google Sheet (Extensions -> Apps Script) and returns the
 * "Invoices 21-22-23-24-25-26" tab as CSV, but only to callers that know KEY.
 * Deployed as a Web app: Execute as = Me, Who has access = Anyone.
 * The sheet itself can then be shared with nobody but the owners.
 */
const KEY = 'PASTE_YOUR_PROXY_KEY_HERE';   // copy PROXY_KEY from .env, never commit the real value
const TAB = 'Invoices 21-22-23-24-25-26';

function doGet(e) {
  const key = e && e.parameter ? e.parameter.key : '';
  if (key !== KEY) {
    return ContentService.createTextOutput('forbidden').setMimeType(ContentService.MimeType.TEXT);
  }
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(TAB);
  if (!sh) return ContentService.createTextOutput('tab not found: ' + TAB).setMimeType(ContentService.MimeType.TEXT);
  const rows = sh.getDataRange().getDisplayValues();
  const csv = rows.map(function (row) {
    return row.map(function (v) {
      v = String(v == null ? '' : v);
      return /[",\r\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
    }).join(',');
  }).join('\r\n');
  return ContentService.createTextOutput(csv).setMimeType(ContentService.MimeType.CSV);
}
