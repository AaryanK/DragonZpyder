package xyz.dragonzpyder.android;

import android.util.Base64;
import java.io.IOException;

final class MediaPayload {
    private MediaPayload(){}
    static byte[] decode(String value,String kind,int limit) throws IOException {
        String prefix;
        if("audio".equals(kind))prefix="data:audio/mpeg;base64,";
        else if("image".equals(kind)){
            if(value.startsWith("data:image/png;base64,"))prefix="data:image/png;base64,";
            else if(value.startsWith("data:image/jpeg;base64,"))prefix="data:image/jpeg;base64,";
            else if(value.startsWith("data:image/webp;base64,"))prefix="data:image/webp;base64,";
            else throw new IOException("Unsupported image response");
        }else throw new IOException("Unsupported media type");
        if(!value.startsWith(prefix)||value.length()-prefix.length()>((long)limit+2)/3*4)throw new IOException("Media response exceeds limit or is invalid");
        try{
            byte[] bytes=Base64.decode(value.substring(prefix.length()),Base64.DEFAULT);
            if(bytes.length==0||bytes.length>limit)throw new IOException("Invalid media size");
            return bytes;
        }catch(IllegalArgumentException e){throw new IOException("Invalid media encoding");}
    }
}
