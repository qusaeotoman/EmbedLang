import embedlang.backend.arm.ArmBackend;
import embedlang.frontend.Frontend;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;

/** Test bridge for Unicode IR filenames, independent of native launcher argv encoding. */
class EmitDebugLines {
    public static void main(String[] args) throws Exception {
        String source = new String(Base64.getDecoder().decode(args[0]), StandardCharsets.UTF_8);
        var result = Frontend.INSTANCE.lower(Files.readString(Path.of(source)), source);
        if (!result.isSuccess()) throw new IllegalStateException(result.getDiagnostics().toString());
        System.out.print(ArmBackend.INSTANCE.emit(result.getIr(), true));
    }
}
