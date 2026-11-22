package xyz.dragonzpyder.android

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.commonmark.ext.gfm.strikethrough.Strikethrough
import org.commonmark.ext.gfm.tables.TableBlock
import org.commonmark.ext.gfm.tables.TableBody
import org.commonmark.ext.gfm.tables.TableCell
import org.commonmark.ext.gfm.tables.TableHead
import org.commonmark.ext.gfm.tables.TableRow
import org.commonmark.node.*
import java.util.Locale

/** Native Compose display of a real CommonMark + GFM AST, not split-on-fences markup. */
@Composable
internal fun MarkdownBody(
    source: String,
    dark: Boolean,
    onCopy: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val doc = remember(source) { MarkdownDocument.parse(source) }
    val palette = remember(dark) { MarkdownColors(dark) }
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        MarkdownDocument.children(doc).forEachIndexed { i, block ->
            androidx.compose.runtime.key(i) { MarkdownBlock(block, palette, onCopy, 0) }
        }
    }
}
private class MarkdownColors(dark: Boolean) {
    val ink = if(dark) Color(0xFFF6F4F1) else Color(0xFF24221F)
    val muted = if(dark) Color(0xFFBFB6AE) else Color(0xFF675F58)
    val panel = if(dark) Color(0xFF242124) else Color(0xFFF6F3EF)
    val code = if(dark) Color(0xFF353034) else Color(0xFFECE7E2)
    val line = if(dark) Color(0xFF594740) else Color(0xFFE0DAD3)
    val accent = if(dark) Color(0xFFFFA477) else Color(0xFFB94A21)
}

@Composable
private fun MarkdownBlock(node: Node, c: MarkdownColors, copy: (String) -> Unit, depth: Int) {
    if(depth >= 20) {
        Text("Content nesting limit reached", color = c.muted, fontSize = 12.sp)
        return
    }
    when(node) {
        is Paragraph -> Text(
            inline(node,c), color=c.ink, fontSize=16.sp, lineHeight=25.sp,
            softWrap=true, overflow=TextOverflow.Clip, modifier=Modifier.fillMaxWidth()
        )
        is Heading -> {
            val font = when(node.level) {1->26.sp;2->22.sp;3->19.sp;else->17.sp}
            Text(
                inline(node,c), color=c.ink, fontSize=font, lineHeight=font * 1.26f,
                fontWeight=FontWeight.SemiBold, softWrap=true,
                modifier=Modifier.fillMaxWidth().padding(top=if(node.level <= 2) 8.dp else 3.dp)
            )
        }
        is FencedCodeBlock -> CodePanel(node.literal, node.info.orEmpty(), c, copy)
        is IndentedCodeBlock -> CodePanel(node.literal, "", c, copy)
        is TableBlock -> MarkdownTable(node,c)
        is BulletList -> MarkdownList(node,false,c,copy,depth)
        is OrderedList -> MarkdownList(node,true,c,copy,depth)
        is BlockQuote -> Row(
            Modifier.fillMaxWidth().height(IntrinsicSize.Min),
            horizontalArrangement=Arrangement.spacedBy(12.dp)
        ){
            Box(Modifier.width(3.dp).fillMaxHeight().background(c.accent, RoundedCornerShape(3.dp)))
            Column(Modifier.weight(1f), verticalArrangement=Arrangement.spacedBy(7.dp)){
                MarkdownDocument.children(node).forEach { MarkdownBlock(it,c,copy,depth+1) }
            }
        }
        is ThematicBreak -> HorizontalDivider(color=c.line, thickness=1.dp,modifier=Modifier.padding(vertical=4.dp))
        is HtmlBlock -> Text(node.literal,color=c.muted,fontSize=14.sp,lineHeight=21.sp)
        else -> MarkdownDocument.children(node).forEach { MarkdownBlock(it,c,copy,depth+1) }
    }
}

@Composable
private fun MarkdownList(list: Node, numbered: Boolean, c: MarkdownColors, copy: (String)->Unit, depth: Int) {
    val start = (list as? OrderedList)?.startNumber ?: 1
    Column(Modifier.fillMaxWidth(), verticalArrangement=Arrangement.spacedBy(6.dp)) {
        MarkdownDocument.children(list).take(300).forEachIndexed { index, item ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement=Arrangement.spacedBy(6.dp)) {
                Text(
                    if(numbered) "${start+index}." else "•",
                    color=c.accent, fontSize=15.sp, lineHeight=24.sp,
                    modifier=Modifier.width(if(numbered) 32.dp else 20.dp)
                )
                Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(5.dp)){
                    MarkdownDocument.children(item).forEach { child ->
                        MarkdownBlock(child,c,copy,depth+1)
                    }
                }
            }
        }
    }
}

@Composable
private fun CodePanel(code: String, info: String, c: MarkdownColors, copy:(String)->Unit) {
    Surface(
        modifier=Modifier.fillMaxWidth(), color=c.panel,
        shape=RoundedCornerShape(12.dp), border=BorderStroke(1.dp,c.line)
    ) {
        Column {
            Row(
                Modifier.fillMaxWidth().heightIn(min=38.dp).padding(start=12.dp,end=6.dp),
                verticalAlignment=Alignment.CenterVertically
            ) {
                val language=info.trim().substringBefore(' ').take(24).ifBlank{"Code"}
                Text(language,color=c.muted,fontSize=12.sp,modifier=Modifier.weight(1f))
                TextButton(onClick={copy(code)},modifier=Modifier.heightIn(min=40.dp)) {
                    Text("Copy code",color=c.accent,fontSize=12.sp)
                }
            }
            HorizontalDivider(color=c.line.copy(alpha=.7f))
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState())) {
                SelectionContainer {
                    Text(
                        text=code.trimEnd('\n'), color=c.ink,
                        fontFamily=FontFamily.Monospace,fontSize=13.sp,lineHeight=20.sp,
                        softWrap=false,modifier=Modifier.padding(12.dp)
                    )
            }
        }
    }
}

private data class TableDisplayRow(val cells:List<TableCell>, val header:Boolean)
private fun tableRows(block:TableBlock): List<TableDisplayRow> {
    val result=ArrayList<TableDisplayRow>()
    for(section in MarkdownDocument.children(block)){
        if(section !is TableHead && section !is TableBody)continue
        val header=section is TableHead
        for(row in MarkdownDocument.children(section)){
            if(row !is TableRow)continue
            result.add(TableDisplayRow(MarkdownDocument.children(row).filterIsInstance<TableCell>().take(12),header))
            if(result.size>=200)return result
        }
    }
    return result
}

@Composable
private fun MarkdownTable(table:TableBlock,c:MarkdownColors) {
    val rows=remember(table) { tableRows(table) }
    val cols=(rows.maxOfOrNull{it.cells.size} ?: 0).coerceIn(0,12)
    if(cols==0)return
    val cellWidth=if(cols <= 2) 155.dp else 175.dp
    Column(Modifier.fillMaxWidth(),verticalArrangement=Arrangement.spacedBy(4.dp)) {
        if(cols>2)Text("Scroll horizontally to view the table",fontSize=11.sp,color=c.muted)
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState())) {
            Column {
                rows.forEachIndexed { index,row ->
                    Row(Modifier.height(IntrinsicSize.Min)) {
                        repeat(cols){ cellIndex ->
                            val cell=row.cells.getOrNull(cellIndex)
                            Box(
                                Modifier.width(cellWidth).fillMaxHeight()
                                    .background(if(row.header)c.panel else if(index%2==0)c.panel.copy(alpha=.40f) else Color.Transparent)
                                    .border(.5.dp,c.line)
                                    .padding(horizontal=10.dp,vertical=9.dp)
                                    .heightIn(min=32.dp),
                                contentAlignment=Alignment.CenterStart
                            ) {
                                Text(
                                    if(cell!=null)inline(cell,c) else AnnotatedString(""),
                                    color=c.ink,fontSize=13.sp,lineHeight=19.sp,
                                    fontWeight=if(row.header)FontWeight.SemiBold else FontWeight.Normal,
                                    softWrap=true,overflow=TextOverflow.Clip
                                )
                            }
                        }
                    }
                }
            }
        }
        if(rows.size==200)Text("Table truncated to 200 rows for device performance",fontSize=11.sp,color=c.muted)
    }
}

private fun inline(parent:Node,c:MarkdownColors):AnnotatedString=buildAnnotatedString {
    fun visit(node:Node,depth:Int) {
        if(depth>50)return
        when(node) {
            is org.commonmark.node.Text -> append(node.literal)
            is Code -> withStyle(SpanStyle(fontFamily=FontFamily.Monospace,background=c.code,color=c.ink)) { append(node.literal) }
            is SoftLineBreak -> append(" ")
            is HardLineBreak -> append("\n")
            is StrongEmphasis -> withStyle(SpanStyle(fontWeight=FontWeight.Bold)) {
                MarkdownDocument.children(node).forEach { visit(it,depth+1) }
            }
            is Emphasis -> withStyle(SpanStyle(fontStyle=FontStyle.Italic)) {
                MarkdownDocument.children(node).forEach { visit(it,depth+1) }
            }
            is Strikethrough -> withStyle(SpanStyle(textDecoration=TextDecoration.LineThrough)) {
                MarkdownDocument.children(node).forEach { visit(it,depth+1) }
            }
            is Link -> withStyle(SpanStyle(color=c.accent,textDecoration=TextDecoration.Underline)) {
                MarkdownDocument.children(node).forEach { visit(it,depth+1) }
            }
            is Image -> { append("[image: ");MarkdownDocument.children(node).forEach{visit(it,depth+1)};append("]") }
            is HtmlInline -> append(node.literal)
            else -> MarkdownDocument.children(node).forEach{visit(it,depth+1)}
        }
    }
    MarkdownDocument.children(parent).forEach { visit(it,0) }
}
