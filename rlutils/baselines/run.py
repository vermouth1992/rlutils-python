from rlutils.infra.runner import get_argparser_from_func

# from rlutils.tf.algos.mb import pets
# from rlutils.tf.algos.mf import td3, ppo, trpo, sac, ddpg, dqn
# from rlutils.tf.algos.offline import cql, plas


__tf__ = ['ppo', 'td3', 'trpo', 'sac', 'ddpg', 'cql', 'plas', 'dqn', 'pets']

__all__ = ['sac_pytorch', 'td3_pytorch', 'atari_dqn_pytorch', 'dqn_pytorch', 'cql_pytorch', 'c51_pytorch',
           'c51_pytorch', 'qr_dqn_pytorch', 'atari_qr_dqn_pytorch']


def main():
    import argparse

    parser = argparse.ArgumentParser('Running rl algorithms', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    algorithm_parsers = parser.add_subparsers(title='algorithm', help='algorithm specific parser', dest='algo')
    for algo in __all__:
        algo_parser = algorithm_parsers.add_parser(algo, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        get_argparser_from_func(eval(f'{algo}.Runner.main'), algo_parser)

    kwargs = vars(parser.parse_args())
    algo = kwargs.pop('algo')
    eval(f'{algo}.Runner.main')(**kwargs)


if __name__ == '__main__':
    main()