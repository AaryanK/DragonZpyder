package xyz.dragonzpyder.android

import android.content.ContentResolver
import android.net.Uri
import android.provider.OpenableColumns
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException

/** No Activity or view references. Call on a background dispatcher. */
internal class AgentFileRepository(private val resolver:ContentResolver,private val api:DragonApi) {
    companion object {
        const val MAX_BYTES=10*1024*1024
        @JvmStatic fun safeFilename(name:String?):Boolean =
            !name.isNullOrBlank() && name.length<=180 && name!="." && name!=".." &&
            name.none{it=='/'||it=='\\'||it.code<32||it.code==127||it.code in 0x202a..0x202e||it.code in 0x2066..0x2069}
        @JvmStatic fun validReceipt(file:JSONObject):Boolean =
            file.optString("id").matches(Regex("[0-9a-f-]{36}")) &&
            file.optString("sha256").matches(Regex("[0-9a-f]{64}")) &&
            safeFilename(file.optString("filename"))
    }

    @Throws(Exception::class)
    fun upload(uri:Uri):JSONObject {
        val mime=resolver.getType(uri)
        val name=resolver.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use{
            if(it.moveToFirst())it.getString(0) else null
        }?:"attachment"
        if(!safeFilename(name))throw IOException("Unsupported filename")
        val bytes=resolver.openInputStream(uri)?.use{input->
            val out=ByteArrayOutputStream()
            val buffer=ByteArray(8192)
            while(true){
                val n=input.read(buffer)
                if(n<0)break
                if(out.size()+n>MAX_BYTES)throw IOException("File exceeds 10 MiB")
                out.write(buffer,0,n)
            }
            out.toByteArray()
        }?:throw IOException("Cannot read file")
        val receipt=api.uploadFile(name,mime,bytes)
        if(!validReceipt(receipt))throw IOException("Invalid file receipt")
        return receipt
    }

    @Throws(Exception::class)
    fun inventory():List<JSONObject> {
        val data=api.call("/dz/v2/personal/files",null) as? JSONObject ?:throw IOException("Invalid file inventory")
        val rows=data.optJSONArray("files")?:throw IOException("Invalid file inventory")
        return (0 until rows.length()).mapNotNull{rows.optJSONObject(it)}.filter{validReceipt(it)}
    }

    @Throws(Exception::class)
    fun save(uri:Uri,file:JSONObject){
        if(!validReceipt(file))throw IOException("Invalid file receipt")
        val data=api.downloadFile(file.getString("id"),file.getString("sha256"))
        resolver.openOutputStream(uri,"w")?.use{it.write(data)}?:throw IOException("Cannot open destination")
    }
}
