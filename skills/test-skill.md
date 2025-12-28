---
name: test-skill
description: Test the new printer CLI and check generation and images are well processed.
---

# New Printer Testing Skill

Test the new_printer CLI tool to verify PDF generation and image incorporation functionality.

## Test URL

Use this article as the standard test case:
- **URL**: https://fromanengineersight.substack.com/p/issue-53-did-marin-mersenne-have
- **Expected**: Article about Marin Mersenne with images

## Instructions

### Step 1: Generate PDF from URL

Run the new_printer CLI to generate a PDF from the test URL:

```bash
uv run new-printer convert https://fromanengineersight.substack.com/p/issue-53-did-marin-mersenne-have
```

**Expected output**:
- CLI should extract content from the URL
- CLI should download any images found in the article
- CLI should generate a PDF file
- Note the output filename and location

### Step 2: Verify PDF Creation

Check that the PDF was successfully created:

```bash
# List the generated PDF file
ls -lh *.pdf

# Check file size (should be > 0 bytes)
du -h *.pdf
```

**Success criteria**:
- PDF file exists
- File size is reasonable (typically > 100KB for articles with images)

### Step 3: Verify Image Incorporation

Check if images are likely embedded by analyzing the PDF file size:

```bash
# Get the PDF file size in KB
ls -lh *.pdf

# A text-only PDF of ~1000 words typically ranges from 50-150KB
# A PDF with images will typically be 300KB+ (depending on image count and quality)
```

**Success criteria**:
- **Text-only PDF**: ~50-150KB (may indicate missing images)
- **PDF with images**: 300KB+ (likely contains embedded images)
- **For the test article**: Should be 500KB+ as it contains multiple images

**Size-based estimation**:
```bash
# Check if PDF is likely to contain images based on size
FILE_SIZE=$(stat -f%z "*.pdf" 2>/dev/null || stat -c%s "*.pdf" 2>/dev/null)
if [ "$FILE_SIZE" -gt 300000 ]; then
  echo "✅ PDF size suggests images are included (${FILE_SIZE} bytes)"
else
  echo "⚠️  PDF size may indicate missing images (${FILE_SIZE} bytes)"
fi
```

### Step 4: Report Results

Summarize the test results:
- ✅ PDF generation: [SUCCESS/FAILURE]
- ✅ Image incorporation: [LIKELY/UNLIKELY] - Based on file size
- ✅ File size: [X KB/MB]
- ⚠️ Any warnings or errors encountered

## Additional Test Cases

After verifying the primary test URL works, you can test with:
- Articles with many images
- Articles with no images
- Different content types (blog posts, news articles, etc.)

## Troubleshooting

If PDF generation fails:
1. Check that the URL is accessible
2. Verify uv is installed: `which uv`
3. Run with verbose output if available: `uv run new-printer convert URL --verbose`
4. Check error messages in the output

If images appear to be missing from PDF (small file size):
1. Check if images were downloaded during extraction (look in logs)
2. Verify image processing in the CLI output
3. Check if the source URL has images available
4. Try opening the PDF to visually confirm image presence
