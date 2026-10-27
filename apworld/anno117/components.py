from worlds.LauncherComponents import Component, Type, components, launch


def run_client(*args: str) -> None:
    from .client import launch_client

    launch(launch_client, name="Anno 117 Client", args=args)


components.append(
    Component(
        "Anno 117 Client",
        func=run_client,
        game_name="Anno 117",
        component_type=Type.CLIENT,
        supports_uri=True,
    )
)
