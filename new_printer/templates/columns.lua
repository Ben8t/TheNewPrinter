-- columns.lua - Pandoc Lua Filter for Multi-Column Layout
-- Enhances multi-column support and provides layout optimizations

local columns = 2  -- Default column count
local in_multicol = false

-- Helper function to check if we're in a multi-column environment
function is_multicolumn()
  return columns > 1
end

-- Function to wrap content in multicol environment
function wrap_in_multicols(content, col_count)
  local begin_multicols = pandoc.RawBlock('latex', '\\begin{multicols}{' .. col_count .. '}')
  local end_multicols = pandoc.RawBlock('latex', '\\end{multicols}')
  
  return {begin_multicols, content, end_multicols}
end

-- Handle images in multi-column layout
-- Don't modify images at all - let Pandoc handle them naturally
-- The template's graphicx settings will handle column width
function Image(img)
  -- Return image unchanged for both single and multi-column
  return img
end

-- Handle tables in multi-column layout
function Table(tbl)
  if is_multicolumn() then
    -- For multi-column layouts, tables might need special handling
    -- Break out of multicols for wide tables if needed
    local table_latex = pandoc.write(pandoc.Pandoc({tbl}), 'latex')
    
    -- Check if table is likely to be too wide
    local col_count = #tbl.colspecs
    if col_count > 3 then
      -- Break out of multicols for wide tables
      return {
        pandoc.RawBlock('latex', '\\end{multicols}'),
        tbl,
        pandoc.RawBlock('latex', '\\begin{multicols}{' .. columns .. '}')
      }
    end
  end
  
  return tbl
end

-- Handle code blocks in multi-column layout
function CodeBlock(cb)
  if is_multicolumn() then
    -- Ensure code blocks don't break across columns poorly
    local latex_code = '\\begin{minipage}{\\columnwidth}\n\\begin{verbatim}\n' .. 
                       cb.text .. '\n\\end{verbatim}\n\\end{minipage}'
    return pandoc.RawBlock('latex', latex_code)
  else
    return cb
  end
end

-- Handle quotes/blockquotes in multi-column layout
function BlockQuote(bq)
  if is_multicolumn() then
    -- Style blockquotes for magazine layout
    local quote_content = pandoc.write(pandoc.Pandoc(bq.content), 'latex')
    local latex_code = '\\begin{quote}\n' .. quote_content .. '\n\\end{quote}'
    return pandoc.RawBlock('latex', latex_code)
  else
    return bq
  end
end

-- Handle horizontal rules
function HorizontalRule()
  if is_multicolumn() then
    -- Use a rule that spans the column width
    return pandoc.RawBlock('latex', '\\rule{\\columnwidth}{0.4pt}')
  else
    return pandoc.RawBlock('latex', '\\rule{\\textwidth}{0.4pt}')
  end
end

-- Handle line breaks in multi-column context
function LineBreak()
  if is_multicolumn() then
    -- Prevent awkward line breaks in narrow columns
    return pandoc.RawInline('latex', '\\\\*')
  else
    return pandoc.LineBreak()
  end
end

-- Optimize paragraph breaks for columns
function Para(para)
  if is_multicolumn() then
    -- Just return the paragraph as-is
    -- Images will be handled by the Image function above
    return para
  else
    return para
  end
end

-- Handle headers in multi-column layout
function Header(header)
  if is_multicolumn() and header.level >= 3 then
    -- For subsections in multi-column, ensure they don't orphan
    local header_latex = '\\needspace{3\\baselineskip}\n'
    local header_content = pandoc.write(pandoc.Pandoc({header}), 'latex')
    return pandoc.RawBlock('latex', header_latex .. header_content)
  else
    return header
  end
end

-- Column break command
function handle_column_break(elem)
  if elem.t == 'RawInline' and elem.format == 'latex' then
    if elem.text == '\\columnbreak' then
      if is_multicolumn() then
        return pandoc.RawInline('latex', '\\columnbreak')
      else
        -- Ignore column breaks in single column mode
        return pandoc.Str('')
      end
    end
  end
  return elem
end

-- Page break handling
function handle_page_break(elem)
  if elem.t == 'RawBlock' and elem.format == 'latex' then
    if elem.text == '\\newpage' or elem.text == '\\pagebreak' then
      if is_multicolumn() then
        -- In multi-column, break out and start new page
        return {
          pandoc.RawBlock('latex', '\\end{multicols}'),
          pandoc.RawBlock('latex', '\\newpage'),
          pandoc.RawBlock('latex', '\\begin{multicols}{' .. columns .. '}')
        }
      else
        return elem
      end
    end
  end
  return elem
end

-- Read metadata to get column count
function Meta(meta)
  if meta.columns then
    columns = tonumber(pandoc.utils.stringify(meta.columns)) or 2
  end
  return meta
end

-- Main filter function
return {
  {Meta = Meta},  -- Process metadata first
  {
    Image = Image,
    Table = Table,
    CodeBlock = CodeBlock,
    BlockQuote = BlockQuote,
    HorizontalRule = HorizontalRule,
    LineBreak = LineBreak,
    Para = Para,
    Header = Header,
    RawInline = handle_column_break,
    RawBlock = handle_page_break
  }
} 