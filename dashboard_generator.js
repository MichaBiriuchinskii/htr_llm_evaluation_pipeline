#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');

/**
 * Generate the React dashboard based on evaluation results
 * @param {string} resultsPath - Path to the JSON results file
 * @param {string} outputDir - Directory to save the dashboard
 */
function generateDashboard(resultsPath, outputDir) {
  // Create output directory if it doesn't exist
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }
  
  console.log(`\nGenerating dashboard in ${outputDir}`);
  
  // Create necessary files for the React app
  // 1. Create package.json
  const packageJson = {
    "name": "htr-evaluation-dashboard",
    "version": "1.0.0",
    "description": "Dashboard for HTR evaluation results",
    "main": "index.js",
    "scripts": {
      "start": "parcel index.html",
      "build": "parcel build index.html"
    },
    "dependencies": {
      "react": "^17.0.2",
      "react-dom": "^17.0.2"
    },
    "devDependencies": {
      "parcel": "^2.0.1"
    }
  };
  
  fs.writeFileSync(
    path.join(outputDir, "package.json"),
    JSON.stringify(packageJson, null, 2)
  );
  
  // 2. Create index.html
  const indexHtml = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HTR Evaluation Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
</head>
<body>
    <div id="root"></div>
    <script type="module" src="./index.js"></script>
</body>
</html>`;
  
  fs.writeFileSync(path.join(outputDir, "index.html"), indexHtml);
  
  // 3. Create index.js
  const indexJs = `import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';

ReactDOM.render(<App />, document.getElementById('root'));`;
  
  fs.writeFileSync(path.join(outputDir, "index.js"), indexJs);
  
  // 4. Create App.js with the dashboard component
  const appJs = `import React from 'react';
import Dashboard from './Dashboard';
import results from './results.json';

const App = () => {
    return <Dashboard results={results} />;
};

export default App;`;
  
  fs.writeFileSync(path.join(outputDir, "App.js"), appJs);
  
  // 5. Copy results.json to the output directory
  fs.copyFileSync(resultsPath, path.join(outputDir, "results.json"));
  
  // 6. Create Dashboard.js component
  const dashboardJs = `import React from 'react';

const Dashboard = ({ results }) => {
  // Color coding for scores
  const getScoreColor = (score) => {
    if (score >= 90) return 'bg-green-500 text-white';
    if (score >= 75) return 'bg-yellow-500 text-white';
    if (score >= 60) return 'bg-orange-500 text-white';
    return 'bg-red-500 text-white';
  };

  // Color coding for error types
  const getErrorTypeColor = (type) => {
    switch(type) {
      case 'critical': return 'bg-red-100 text-red-800';
      case 'semantic': return 'bg-yellow-100 text-yellow-800';
      case 'minor': return 'bg-blue-100 text-blue-800';
      case 'perfect': return 'bg-green-100 text-green-800';
      default: return '';
    }
  };

  return (
    <div className="p-4 max-w-5xl mx-auto bg-white rounded-lg shadow">
      <h1 className="text-2xl font-bold mb-6">HTR Evaluation Dashboard</h1>
      
      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-100 p-4 rounded-lg text-center">
          <p className="text-gray-500 text-sm">Overall Score</p>
          <div className={\`text-2xl font-bold my-2 py-2 rounded \${getScoreColor(results.final_score)}\`}>
            {results.final_score.toFixed(1)}%
          </div>
        </div>
        
        <div className="bg-gray-100 p-4 rounded-lg text-center">
          <p className="text-gray-500 text-sm">Field Coverage</p>
          <div className={\`text-2xl font-bold my-2 py-2 rounded \${getScoreColor(results.field_coverage)}\`}>
            {results.field_coverage.toFixed(1)}%
          </div>
        </div>
        
        <div className="bg-gray-100 p-4 rounded-lg text-center">
          <p className="text-gray-500 text-sm">Critical Errors</p>
          <div className="text-2xl font-bold my-2 py-2 rounded bg-red-100 text-red-800">
            {results.error_categories.critical}%
          </div>
        </div>
        
        <div className="bg-gray-100 p-4 rounded-lg text-center">
          <p className="text-gray-500 text-sm">Perfect Matches</p>
          <div className="text-2xl font-bold my-2 py-2 rounded bg-green-100 text-green-800">
            {results.error_categories.perfect}%
          </div>
        </div>
      </div>
      
      {/* Error Distribution */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold mb-3">Error Distribution</h2>
        <div className="h-8 w-full rounded-lg overflow-hidden flex">
          <div 
            className="bg-red-500 h-full" 
            style={{width: \`\${results.error_categories.critical}%\`}}
            title={\`Critical: \${results.error_categories.critical}%\`}
          ></div>
          <div 
            className="bg-yellow-500 h-full" 
            style={{width: \`\${results.error_categories.semantic}%\`}}
            title={\`Semantic: \${results.error_categories.semantic}%\`}
          ></div>
          <div 
            className="bg-blue-400 h-full" 
            style={{width: \`\${results.error_categories.minor}%\`}}
            title={\`Minor: \${results.error_categories.minor}%\`}
          ></div>
          <div 
            className="bg-green-500 h-full" 
            style={{width: \`\${results.error_categories.perfect}%\`}}
            title={\`Perfect: \${results.error_categories.perfect}%\`}
          ></div>
        </div>
        <div className="flex text-xs mt-1 text-gray-600 justify-between">
          <span>Critical ({results.error_categories.critical}%)</span>
          <span>Semantic ({results.error_categories.semantic}%)</span>
          <span>Minor ({results.error_categories.minor}%)</span>
          <span>Perfect ({results.error_categories.perfect}%)</span>
        </div>
      </div>
      
      {/* Top Errors Table */}
      <div>
        <h2 className="text-xl font-semibold mb-3">All Errors ({results.detailed_errors.length})</h2>
        <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
            <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Field</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Gold Standard</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">HTR Output</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Error Type</th>
            </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
            {results.detailed_errors.map((error, index) => (
                <tr key={index}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{error.field}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{String(error.gold)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{String(error.pred || '-')}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={\`px-2 inline-flex text-xs leading-5 font-semibold rounded-full \${getErrorTypeColor(error.type)}\`}>
                      {error.type.charAt(0).toUpperCase() + error.type.slice(1)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;`;
  
  fs.writeFileSync(path.join(outputDir, "Dashboard.js"), dashboardJs);
  
  console.log(`Dashboard files created in ${outputDir}`);
  return path.join(outputDir, "index.html");
}

/**
 * Launch the dashboard using npm
 * @param {string} dashboardDir - Path to the dashboard directory
 */
function launchDashboard(dashboardDir) {
  const originalDir = process.cwd();
  
  try {
    // Change to the dashboard directory
    process.chdir(dashboardDir);
    
    console.log(`\nSetting up and launching dashboard from ${dashboardDir}`);
    
    // Run npm install
    console.log("Installing dependencies (npm install)...");
    execSync('npm install', { stdio: 'inherit' });
    
    // Display access instructions
    console.log("\n" + "=".repeat(60));
    console.log("DASHBOARD ACCESS INSTRUCTIONS:");
    console.log("=".repeat(60));
    console.log("Once the server starts:");
    console.log("1. Open your web browser");
    console.log("2. Navigate to: http://localhost:1234");
    console.log("=".repeat(60));
    console.log("\nPress Ctrl+C to stop the server when done.");
    
    // Start the parcel server
    console.log("\nStarting Parcel development server (npm start)...");
    const npmStart = spawn('npm', ['start'], { 
      stdio: 'inherit',
      shell: true 
    });
    
    // Handle server process events
    npmStart.on('error', (err) => {
      console.error(`Error starting npm: ${err}`);
    });
    
    npmStart.on('close', (code) => {
      console.log(`Server process exited with code ${code}`);
      // Change back to original directory
      process.chdir(originalDir);
    });
    
  } catch (error) {
    console.error(`Error running npm commands: ${error}`);
    // Ensure we change back to the original directory in case of error
    process.chdir(originalDir);
  }
}

/**
 * Main function to run the dashboard generator
 */
function main() {
  // Get command line arguments
  const args = process.argv.slice(2);
  
  if (args.length < 2) {
    console.error("Usage: node dashboard_generator.js <results_json_path> <output_dir>");
    process.exit(1);
  }
  
  const resultsPath = args[0];
  const outputDir = args[1];
  
  // Check if results file exists
  if (!fs.existsSync(resultsPath)) {
    console.error(`Error: Results file not found at ${resultsPath}`);
    process.exit(1);
  }
  
  // Generate dashboard
  const htmlPath = generateDashboard(resultsPath, outputDir);
  
  // Launch dashboard
  launchDashboard(outputDir);
}

// Run the main function if this script is called directly
if (require.main === module) {
  main();
}

// Export functions for potential reuse in other scripts
module.exports = {
  generateDashboard,
  launchDashboard
};
