use zed_extension_api::{self as zed, serde_json::{self, Value}};

struct EmbedLangDebugger;

// This is Zed API glue only. CDT implements DAP; GDB implements source debugging.
fn binary(mut config: Value) -> Result<zed::DebugAdapterBinary, String> {
    if config["request"] != "launch" || config["target"]["host"] != "127.0.0.1"
        || config["target"]["type"] != "remote" {
        return Err("Use the generated local Unicorn launch configuration".into());
    }
    let required = |key: &str| -> Result<String, String> {
        config[key].as_str().filter(|s| !s.is_empty()).map(str::to_owned)
            .ok_or_else(|| format!("Missing {key}; run node extensions/zed/debug.js first"))
    };
    let node = required("nodePath")?;
    let adapter = required("cdtAdapterPath")?;
    let cwd = required("cwd")?;
    required("program")?;
    required("gdb")?;
    let object = config.as_object_mut().ok_or("Expected configuration object")?;
    for key in ["nodePath", "cdtAdapterPath", "adapter", "label"] { object.remove(key); }
    Ok(zed::DebugAdapterBinary {
        command: Some(node), arguments: vec![adapter], envs: vec![], cwd: Some(cwd),
        connection: None,
        request_args: zed::StartDebuggingRequestArguments {
            configuration: config.to_string(),
            request: zed::StartDebuggingRequestArgumentsRequest::Launch,
        },
    })
}

impl zed::Extension for EmbedLangDebugger {
    fn new() -> Self { Self }

    fn get_dap_binary(&mut self, name: String, config: zed::DebugTaskDefinition,
        _user_path: Option<String>, _worktree: &zed::Worktree) -> Result<zed::DebugAdapterBinary, String> {
        if name != "EmbedLang GDB" { return Err("Unknown debug adapter".into()); }
        if config.tcp_connection.is_some() { return Err("Use stdio DAP; the target's TCP port speaks RSP".into()); }
        binary(serde_json::from_str(&config.config).map_err(|e| e.to_string())?)
    }

    fn dap_request_kind(&mut self, name: String, config: Value)
        -> Result<zed::StartDebuggingRequestArgumentsRequest, String> {
        if name != "EmbedLang GDB" || config["request"] != "launch" {
            return Err("EmbedLang GDB requires a local launch scenario".into());
        }
        Ok(zed::StartDebuggingRequestArgumentsRequest::Launch)
    }
}

zed::register_extension!(EmbedLangDebugger);

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn config() -> Value {
        json!({"request":"launch", "nodePath":"/node", "cdtAdapterPath":"/cdt.js",
            "cwd":"/workspace", "program":"/program.elf", "gdb":"/gdb",
            "target":{"host":"127.0.0.1", "type":"remote"}})
    }

    #[test]
    fn produces_stdio_adapter_and_preserves_launch_fields() {
        let result = binary(config()).unwrap();
        assert_eq!(result.command.as_deref(), Some("/node"));
        assert_eq!(result.arguments, vec!["/cdt.js"]);
        assert!(result.connection.is_none());
        let launch: Value = serde_json::from_str(&result.request_args.configuration).unwrap();
        assert_eq!(launch["program"], "/program.elf");
        assert!(launch.get("nodePath").is_none());
    }

    #[test]
    fn rejects_wrong_target_and_missing_executables() {
        let mut value = config(); value["target"]["host"] = json!("192.0.2.1");
        assert!(binary(value).is_err());
        let mut value = config(); value["nodePath"] = Value::Null;
        assert!(binary(value).is_err());
    }
}
