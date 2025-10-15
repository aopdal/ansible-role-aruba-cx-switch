// Initialize Mermaid diagrams
document$.subscribe(function () {
    mermaid.initialize({
        startOnLoad: true,
        theme: 'default',
        securityLevel: 'loose',
        themeVariables: {
            primaryColor: '#5c6bc0',
            primaryTextColor: '#fff',
            primaryBorderColor: '#3f51b5',
            lineColor: '#9e9e9e',
            secondaryColor: '#81c784',
            tertiaryColor: '#fff'
        }
    });

    // Re-render diagrams on page navigation
    mermaid.contentLoaded();
});
