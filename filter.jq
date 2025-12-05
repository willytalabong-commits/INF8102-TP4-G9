.Results[]?
| .Vulnerabilities? // []
| map(select(.Severity == "HIGH" or .Severity == "CRITICAL"))
| map({
    ID: .VulnerabilityID,
    Title: .Title,
    Description: .Description,
    Severity: .Severity,
    CVSSv3: ( (.CVSS // {}) | to_entries[]? | .value.V3Vector ) // null
})