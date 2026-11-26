package xyz.dragonzpyder.android

internal object MathMarkup {
    data class Formula(val latex:String,val display:Boolean,val raw:String)
    data class Document(val source:String,val formulas:Map<String,Formula>)
    private val token=Regex("DZMATHTOKEN[0-9]+END")
    fun extract(source:String):Document {
        if(token.containsMatchIn(source)) return Document(source,emptyMap())
        val formulas=linkedMapOf<String,Formula>()
        val output=StringBuilder()
        var i=0
        var fence:Char?=null
        var fenceWidth=0
        var inlineTicks=0
        val tick=96.toChar()
        fun escaped(index:Int):Boolean {
            var k=index-1
            while(k>=0&&source[k]=='\\')k--
            return (index-1-k)%2==1
        }
        while(i<source.length){
            if(i==0||source[i-1]=='\n'){
                val lineEnd=source.indexOf('\n',i).let{if(it<0)source.length else it+1}
                val line=source.substring(i,lineEnd)
                val trimmed=line.trimStart(' ')
                val indent=line.length-trimmed.length
                val mark=trimmed.firstOrNull()
                val width=if(mark==tick||mark=='~')trimmed.takeWhile{it==mark}.length else 0
                if(indent<=3&&width>=3&&(fence==null||(fence==mark&&width>=fenceWidth))){
                    if(fence==null){fence=mark;fenceWidth=width}else{fence=null;fenceWidth=0}
                    inlineTicks=0
                    output.append(line);i=lineEnd;continue
                }
                if(fence!=null||indent>=4||line.startsWith('\t')){output.append(line);i=lineEnd;continue}
            }
            if(fence!=null){output.append(source[i++]);continue}
            if(source[i]==tick&&!escaped(i)){
                var n=1
                while(i+n<source.length&&source[i+n]==tick)n++
                if(inlineTicks==0)inlineTicks=n else if(inlineTicks==n)inlineTicks=0
                output.append(source,i,i+n);i+=n;continue
            }
            if(inlineTicks!=0||escaped(i)||formulas.size>=64){output.append(source[i++]);continue}
            val open=when {
                source.startsWith("\\[",i)->"\\["
                source.startsWith("\\(",i)->"\\("
                source.startsWith("$$",i)->"$$"
                source[i]=='$'&&i+1<source.length&&!source[i+1].isWhitespace()&&!source[i+1].isDigit()->"$"
                else->null
            }
            if(open==null){output.append(source[i++]);continue}
            val close=when(open){"\\["->"\\]";"\\("->"\\)";else->open}
            val display=open=="\\["||open=="$$"
            val start=i+open.length
            var end=source.indexOf(close,start)
            while(end>=0&&end-start<=2048&&escaped(end))end=source.indexOf(close,end+close.length)
            if(end<=start||end-start>2048||(!display&&source.substring(start,end).contains('\n'))||
                (open=="$"&&(source[end-1].isWhitespace()||source.getOrNull(end+1)?.isDigit()==true))){
                output.append(source[i++]);continue
            }
            val raw=source.substring(i,end+close.length)
            val id="DZMATHTOKEN"+formulas.size+"END"
            formulas[id]=Formula(source.substring(start,end),display,raw)
            output.append(id)
            i=end+close.length
        }
        return Document(output.toString(),formulas)
    }
}
