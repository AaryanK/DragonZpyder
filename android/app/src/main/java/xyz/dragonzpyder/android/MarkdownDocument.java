package xyz.dragonzpyder.android;

import org.commonmark.ext.autolink.AutolinkExtension;
import org.commonmark.ext.gfm.strikethrough.StrikethroughExtension;
import org.commonmark.ext.gfm.tables.TablesExtension;
import org.commonmark.node.*;
import org.commonmark.parser.Parser;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** A real, GFM-capable document parser. Never renders raw HTML or opens URLs. */
public final class MarkdownDocument {
    private static final Parser PARSER=Parser.builder().extensions(Arrays.asList(
        TablesExtension.create(),StrikethroughExtension.create(),AutolinkExtension.create())).build();
    public static final int MAX_CHARS=100_000;
    private MarkdownDocument(){}
    public static Node parse(String source){
        String value=source==null?"":source;
        if(value.length()>MAX_CHARS)value=value.substring(0,MAX_CHARS)+"\n\n[Long reply truncated for safe rendering]";
        return PARSER.parse(value);
    }
    public static List<Node> children(Node parent){
        List<Node> nodes=new ArrayList<>();
        for(Node n=parent.getFirstChild();n!=null&&nodes.size()<10000;n=n.getNext())nodes.add(n);
        return nodes;
    }
    /** Used only for table/model accessibility and tests, not a Markdown renderer. */
    public static String plain(Node root){
        StringBuilder text=new StringBuilder();
        plainInto(root,text,0);
        return text.toString();
    }
    private static void plainInto(Node root,StringBuilder out,int depth){
        if(depth>80||out.length()>MAX_CHARS)return;
        if(root instanceof Text)out.append(((Text)root).getLiteral());
        else if(root instanceof Code)out.append(((Code)root).getLiteral());
        else if(root instanceof FencedCodeBlock)out.append(((FencedCodeBlock)root).getLiteral());
        else if(root instanceof IndentedCodeBlock)out.append(((IndentedCodeBlock)root).getLiteral());
        else if(root instanceof SoftLineBreak)out.append(' ');
        else if(root instanceof HardLineBreak)out.append('\n');
        else if(root instanceof HtmlInline)out.append(((HtmlInline)root).getLiteral());
        else if(root instanceof HtmlBlock)out.append(((HtmlBlock)root).getLiteral());
        else for(Node n=root.getFirstChild();n!=null;n=n.getNext())plainInto(n,out,depth+1);
    }
}
