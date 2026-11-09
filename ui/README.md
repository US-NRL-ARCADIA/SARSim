# Getting Started with Create React App

## Action script playback

The SARSim console includes an **Action Script** editor. Use a script object to
choose an authored environment, set the delay between actions, and list actions.
Choose **Play Script** to load the environment first, then execute each action
in order, advancing one simulation tick per action. The delay keeps each result
visible before playback advances.

```json
{
  "environment": "editor/action_script_all_features.json",
  "delay_ms": 1500,
  "actions": [
    { "actor_id": "A1", "action_type": "TRIAGE", "target_casualty_id": "C1", "label": "Triage C1" },
    { "actor_id": "A1", "action_type": "LOAD_CASUALTY", "target_casualty_id": "C1" }
  ]
}
```

`environment` is an optional path to an authored scenario JSON file. `delay_ms`
is optional, defaults to 1000, and accepts values from 0 to 10000. A legacy JSON
array of actions is also accepted and uses a 1000 ms delay. The default script
is `src/all_features_demo_script.json`; it runs against
`editor/action_script_all_features.json`. The page loads this environment on
startup, and relative scenario paths resolve from the project root when the API
is launched from another working directory. The 10×10 map separates three
corner challenges: wall navigation, a smoke/debris search with multiple
casualties, and debris clearance to reach covered casualties. It also includes
a separate building breach and recovery of a deceased casualty. The scenario
and default script each use one UGV and one shared field hospital.

Each action uses the API action shape. `actor_id` and `action_type` are
required. `target_casualty_id` is used by `TRIAGE`, `LOAD_CASUALTY`, and
`RETRIEVE_BODY`; `target_coord` is used by `CLEAR_DEBRIS` and
`BREACH_ENTRYWAY`. A `label` is optional and appears in the playback status.
Supported action types include `MOVE_FORWARD`, `TRIAGE`, `CLEAR_DEBRIS`,
`RETRIEVE_BODY`, `LOAD_CASUALTY`, `UNLOAD_CASUALTY`, `TRANSFER_CASUALTY`,
`BREACH_ENTRYWAY`, `ASCEND`, `DESCEND`, `TURN_LEFT`, and `TURN_RIGHT`.

## Keyboard controls

Select the agent, then use `W`, `A`, `S`, and `D` to move north, west, south,
and east. Movement turns the agent toward that direction and advances one
tile. Press `Space` to interact with the tile directly ahead: it clears debris,
triages or loads a casualty, retrieves a body, breaches a building, or transfers
a carried casualty at the field hospital when appropriate. The matching action
button briefly highlights after each key press. A blue triangle on the agent
shows its facing direction.

Legacy array example:

```json
[
  { "actor_id": "A1", "action_type": "TRIAGE", "target_casualty_id": "C1", "label": "Triage C1" },
  { "actor_id": "A1", "action_type": "LOAD_CASUALTY", "target_casualty_id": "C1" },
  { "actor_id": "A1", "action_type": "TURN_RIGHT" },
  { "actor_id": "A1", "action_type": "MOVE_FORWARD" }
]
```

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

The page will reload if you make edits.\
You will also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can’t go back!**

If you aren’t satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you’re on your own.

You don’t have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn’t feel obligated to use this feature. However we understand that this tool wouldn’t be useful if you couldn’t customize it when you are ready for it.

## Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).
