import "dotenv/config";
import OpenAI from "openai";
import { execSync } from "child_process";
import * as fs from "fs";
import * as path from "path";

const client = new OpenAI({
  baseURL: "https://openrouter.ai/api/v1",
  apiKey: process.env.OPENROUTER_API_KEY,
});

const PDF_FOLDER = "./pdfs";
const RESULTS_FOLDER = "./results";
const PAGES_FOLDER = "./pages";
const CSV_FILE = "./database.csv";

fs.mkdirSync(RESULTS_FOLDER, { recursive: true });
fs.mkdirSync(PAGES_FOLDER, { recursive: true });

// Write CSV header
fs.writeFileSync(CSV_FILE, "filename,page,type,label,row,column,unit,value\n");

const pdfFiles = fs.readdirSync(PDF_FOLDER).filter(f => f.endsWith(".pdf"));
console.log(`Found ${pdfFiles.length} PDF(s) to process...`);

function escapeCSV(val) {
  if (val === null || val === undefined) return "";
  const str = String(val);
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function appendToCSV(filename, page, type, label, row, column, unit, value) {
  const line = [filename, page, type, label, row, column, unit, value]
    .map(escapeCSV)
    .join(",") + "\n";
  fs.appendFileSync(CSV_FILE, line);
}

for (const pdfFile of pdfFiles) {
  const pdfPath = path.join(PDF_FOLDER, pdfFile);
  const pdfName = path.basename(pdfFile, ".pdf");

  console.log(`\n=============================`);
  console.log(`Processing: ${pdfFile}`);
  console.log(`=============================`);

  const pdfPagesDir = path.join(PAGES_FOLDER, pdfName);
  fs.mkdirSync(pdfPagesDir, { recursive: true });
  execSync(`pdftoppm -png -r 200 "${pdfPath}" "${pdfPagesDir}/page"`);

  const pages = fs.readdirSync(pdfPagesDir).sort();

  for (const page of pages) {
    const pageNum = page.replace(/\D/g, "");
    const imagePath = path.join(pdfPagesDir, page);
    const imageBase64 = fs.readFileSync(imagePath).toString("base64");

    console.log(`  → Page ${pageNum}`);

    let completion;
    try {
      completion = await client.chat.completions.create({
        model: "google/gemini-2.5-flash",
        messages: [{
          role: "user",
          content: [
            {
              type: "image_url",
              image_url: { url: `data:image/png;base64,${imageBase64}` }
            },
            {
              type: "text",
              text: `You are a scientific data extractor. Extract ALL data from tables and figures on this page.
Return ONLY a JSON array, no explanation, no markdown, no backticks.
Each item in the array represents one data point with this structure:
{
  "type": "table" or "figure",
  "label": "full caption or title of the table/figure",
  "row": row number as integer (1-based),
  "column": "column header name",
  "unit": "unit of measurement or empty string",
  "value": "the cell value as string"
}
If there are no tables or figures on this page, return an empty array: []`
            }
          ]
        }],
      });
    } catch (err) {
      console.log(`    ⚠ API error on page ${pageNum}: ${err.message}`);
      continue;
    }

    let raw = completion.choices[0].message.content.trim();

    // Strip markdown code fences if present
    raw = raw.replace(/^```json\s*/i, "").replace(/^```\s*/i, "").replace(/```$/i, "").trim();

    let data;
    try {
      data = JSON.parse(raw);
    } catch (e) {
      console.log(`    ⚠ Could not parse JSON on page ${pageNum}, saving raw to results/`);
      fs.writeFileSync(path.join(RESULTS_FOLDER, `${pdfName}_page${pageNum}_raw.txt`), raw);
      continue;
    }

    if (!Array.isArray(data) || data.length === 0) {
      console.log(`    → No tables or figures on page ${pageNum}`);
      continue;
    }

    for (const item of data) {
      appendToCSV(
        pdfFile,
        pageNum,
        item.type || "",
        item.label || "",
        item.row || "",
        item.column || "",
        item.unit || "",
        item.value || ""
      );
    }

    console.log(`    ✓ Extracted ${data.length} data points`);
  }
}

console.log(`\n✅ Done! All data saved to ${CSV_FILE}`);