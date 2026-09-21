/**
 * WBR sales dashboard relay.
 * Lives inside the Google Sheet (Extensions -> Apps Script) and returns the
 * "Invoices 21-22-23-24-25-26" tab as CSV, but only to callers that know KEY.
 * Deployed as a Web app: Execute as = Me, Who has access = Anyone.
 * The sheet itself can then be shared with nobody but the owners.
 */
const KEY = 'PASTE_YOUR_PROXY_KEY_HERE';   // copy PROXY_KEY from .env, never commit the real value
const TAB = 'Invoices 21-22-23-24-25-26';
// Seller tokens: each returns only the lines whose SELLER cell names that seller.
// Copy the "token" values from SELLERS_JSON in .env.
const SELLER_TOKENS = {
  'PASTE_TOKEN_SERGIO': 'SERGIO',
  'PASTE_TOKEN_MIGUEL': 'MIGUEL',
  'PASTE_TOKEN_JASON': 'JASON'
};

function doGet(e) {
  const key = e && e.parameter ? e.parameter.key : '';
  const seller = SELLER_TOKENS[key] || null;
  if (key !== KEY && !seller) {
    return ContentService.createTextOutput('forbidden').setMimeType(ContentService.MimeType.TEXT);
  }
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(TAB);
  if (!sh) return ContentService.createTextOutput('tab not found: ' + TAB).setMimeType(ContentService.MimeType.TEXT);
  let rows = sh.getDataRange().getDisplayValues();
  if (seller) {
    const col = rows[0].map(function (h) { return String(h).trim().toUpperCase(); }).indexOf('SELLER');
    rows = [rows[0]].concat(rows.slice(1).filter(function (r) {
      return String(r[col] || '').toUpperCase().replace('JAMIE', 'JAIME').split('/').map(function (p) { return p.trim(); }).indexOf(seller) >= 0;
    }));
  }
  const csv = rows.map(function (row) {
    return row.map(function (v) {
      v = String(v == null ? '' : v);
      return /[",\r\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
    }).join(',');
  }).join('\r\n');
  return ContentService.createTextOutput(csv).setMimeType(ContentService.MimeType.CSV);
}
