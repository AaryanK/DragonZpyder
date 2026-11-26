package xyz.dragonzpyder.android

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties

internal data class CommandItem(val title:String,val icon:String,val action:Runnable)

@Composable internal fun NativeCommandPalette(
    commands:List<CommandItem>,dark:Boolean,onDismiss:()->Unit
){
    var query by remember{mutableStateOf("")}
    val tokens=DragonDesignTokens.of(dark)
    val filtered=commands.filter{it.title.contains(query.trim(),ignoreCase=true)}
    Dialog(onDismissRequest=onDismiss,properties=DialogProperties(usePlatformDefaultWidth=false)){
        DragonTheme(dark){
            Surface(Modifier.padding(16.dp).widthIn(max=520.dp).fillMaxWidth(),shape=RoundedCornerShape(24.dp),color=tokens.surface){
                Column(Modifier.padding(16.dp).heightIn(max=560.dp)){
                    Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                        Text("More actions",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.SemiBold,modifier=Modifier.weight(1f).semantics{heading()})
                        IconButton(onClick=onDismiss,modifier=Modifier.size(DragonSizes.touch).semantics{contentDescription="Close commands"}){NavigationGlyph("close",tokens.ink)}
                    }
                    OutlinedTextField(value=query,onValueChange={query=it},label={Text("Search actions")},singleLine=true,leadingIcon={NavigationGlyph("search",tokens.muted)},modifier=Modifier.fillMaxWidth())
                    Spacer(Modifier.height(8.dp))
                    LazyColumn(Modifier.weight(1f,fill=false)){
                        if(filtered.isEmpty())item{Text("No matching commands",color=tokens.muted,modifier=Modifier.padding(12.dp))}
                        items(filtered,key={it.title}){command->
                            DragonNavigationRow(command.title,command.icon,dark){onDismiss();command.action.run()}
                        }
                    }
                }
            }
        }
    }
}
