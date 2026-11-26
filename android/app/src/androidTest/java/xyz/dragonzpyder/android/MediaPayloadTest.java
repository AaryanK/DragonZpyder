package xyz.dragonzpyder.android;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class MediaPayloadTest {
    @Test public void boundedMedia() throws Exception {
        assertArrayEquals(new byte[]{1,2,3},MediaPayload.decode("data:audio/mpeg;base64,AQID","audio",3));
        assertArrayEquals(new byte[]{1,2,3},MediaPayload.decode("data:image/png;base64,AQID","image",3));
    }
    @Test public void rejectedPayloads(){
        for(String value:new String[]{"https://example.com","data:image/svg+xml;base64,AQID","data:image/png;base64,AQID","data:image/png;base64,!"}){
            try{MediaPayload.decode(value,"image",2);fail("Unsafe payload accepted");}catch(java.io.IOException expected){}
        }
    }
}
